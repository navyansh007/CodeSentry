"""
RAG System - ChromaDB integration with advanced context retrieval
"""

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
import hashlib
import json


class RAGSystem:
    """RAG system using ChromaDB for code embeddings and retrieval"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.embedding_model_name = config['embeddings']['model_name']
        self.persist_dir = config['chromadb']['persist_directory']
        self.collection_name = config['chromadb']['collection_name']
        self.top_k = config['rag']['top_k_results']
        self.similarity_threshold = config['rag']['similarity_threshold']

        print(f"Initializing RAG system with {self.embedding_model_name}...")

        # Initialize embedding model
        self.embedding_model = SentenceTransformer(self.embedding_model_name)

        # Initialize ChromaDB
        self.client = chromadb.Client(Settings(
            persist_directory=self.persist_dir,
            anonymized_telemetry=False
        ))

        # Get or create collection
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
            print(f"Using existing collection: {self.collection_name}")
        except:
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Code embeddings for review"}
            )
            print(f"Created new collection: {self.collection_name}")

    def index_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """Index code chunks into ChromaDB"""
        if not chunks:
            print("No chunks to index")
            return

        print(f"Indexing {len(chunks)} chunks into ChromaDB...")

        # Clear existing collection
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Code embeddings for review"}
            )
        except:
            pass

        # Prepare data for indexing
        documents = []
        metadatas = []
        ids = []

        for idx, chunk in enumerate(chunks):
            content = chunk['content']
            documents.append(content)

            # Create metadata
            metadata = {
                'file_path': chunk['file_path'],
                'file_name': chunk['file_name'],
                'chunk_type': chunk['chunk_type'],
                'start_line': chunk['start_line'],
                'end_line': chunk['end_line'],
            }

            # Add optional metadata
            if 'structure_type' in chunk:
                metadata['structure_type'] = chunk['structure_type']
                metadata['structure_name'] = chunk['structure_name']

            metadatas.append(metadata)

            # Generate unique ID
            chunk_id = self._generate_chunk_id(chunk, idx)
            ids.append(chunk_id)

        # Generate embeddings
        print("  Generating embeddings...")
        embeddings = self.embedding_model.encode(
            documents,
            show_progress_bar=True,
            convert_to_numpy=True
        ).tolist()

        # Add to ChromaDB in batches
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            end_idx = min(i + batch_size, len(documents))

            self.collection.add(
                embeddings=embeddings[i:end_idx],
                documents=documents[i:end_idx],
                metadatas=metadatas[i:end_idx],
                ids=ids[i:end_idx]
            )

        print(f"  Successfully indexed {len(documents)} chunks")

    def retrieve_context(self, query: str, n_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve relevant code chunks for a query"""
        if n_results is None:
            n_results = self.top_k

        # Generate query embedding
        query_embedding = self.embedding_model.encode([query]).tolist()

        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results
        )

        # Format results
        context_chunks = []
        if results['documents'] and results['documents'][0]:
            for idx, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][idx]
                distance = results['distances'][0][idx] if 'distances' in results else None

                # Filter by similarity threshold
                if distance is not None and distance > self.similarity_threshold:
                    continue

                context_chunks.append({
                    'content': doc,
                    'metadata': metadata,
                    'similarity_score': 1 - distance if distance is not None else 1.0
                })

        return context_chunks

    def retrieve_file_context(self, file_path: str) -> List[Dict[str, Any]]:
        """Retrieve all chunks for a specific file"""
        results = self.collection.get(
            where={"file_path": file_path}
        )

        context_chunks = []
        if results['documents']:
            for idx, doc in enumerate(results['documents']):
                context_chunks.append({
                    'content': doc,
                    'metadata': results['metadatas'][idx]
                })

        return context_chunks

    def retrieve_by_structure(self, structure_name: str) -> List[Dict[str, Any]]:
        """Retrieve chunks for a specific function/class"""
        results = self.collection.get(
            where={"structure_name": structure_name}
        )

        context_chunks = []
        if results['documents']:
            for idx, doc in enumerate(results['documents']):
                context_chunks.append({
                    'content': doc,
                    'metadata': results['metadatas'][idx]
                })

        return context_chunks

    def get_diverse_samples(self, n_samples: int = 10) -> List[Dict[str, Any]]:
        """Get diverse code samples from different files for general review"""
        # Get all unique file paths
        all_results = self.collection.get()

        if not all_results['metadatas']:
            return []

        # Group by file
        file_chunks = {}
        for idx, metadata in enumerate(all_results['metadatas']):
            file_path = metadata['file_path']
            if file_path not in file_chunks:
                file_chunks[file_path] = []
            file_chunks[file_path].append({
                'content': all_results['documents'][idx],
                'metadata': metadata
            })

        # Sample from each file
        samples = []
        files_list = list(file_chunks.keys())

        for file_path in files_list[:n_samples]:
            if file_chunks[file_path]:
                # Take first chunk from each file
                samples.append(file_chunks[file_path][0])

        return samples

    def _generate_chunk_id(self, chunk: Dict[str, Any], idx: int) -> str:
        """Generate unique ID for a chunk"""
        id_string = f"{chunk['file_path']}_{chunk['start_line']}_{chunk['end_line']}_{idx}"
        return hashlib.md5(id_string.encode()).hexdigest()

    def clear_collection(self) -> None:
        """Clear the ChromaDB collection"""
        try:
            self.client.delete_collection(name=self.collection_name)
            print(f"Cleared collection: {self.collection_name}")
        except Exception as e:
            print(f"Error clearing collection: {str(e)}")
