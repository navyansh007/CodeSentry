"""
Code Indexer - Chunks and indexes code for embedding
"""

import os
from typing import List, Dict, Any, Tuple
import re
from pathlib import Path


class CodeIndexer:
    """Indexes code files into chunks for embedding"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.chunk_size = config['embeddings']['chunk_size']
        self.chunk_overlap = config['embeddings']['chunk_overlap']
        self.chunks = []

    def index_files(self, files: List[str]) -> List[Dict[str, Any]]:
        """Index all files and create chunks"""
        print(f"Indexing {len(files)} files...")

        for file_path in files:
            try:
                self._index_file(file_path)
            except Exception as e:
                print(f"  Error indexing {file_path}: {str(e)}")

        print(f"Created {len(self.chunks)} code chunks")
        return self.chunks

    def _index_file(self, file_path: str) -> None:
        """Index a single file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"  Could not read {file_path}: {str(e)}")
            return

        # Get file metadata
        file_info = {
            'path': file_path,
            'name': os.path.basename(file_path),
            'extension': os.path.splitext(file_path)[1],
            'size': len(content)
        }

        # Extract functions and classes
        structures = self._extract_code_structures(content, file_path)

        # Chunk the file
        chunks = self._chunk_file(content, file_info, structures)
        self.chunks.extend(chunks)

    def _extract_code_structures(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract functions, classes, and other code structures"""
        structures = []
        ext = os.path.splitext(file_path)[1]

        if ext == '.py':
            # Extract Python functions and classes
            # Function pattern
            func_pattern = r'^(def\s+(\w+)\s*\([^)]*\):)'
            for match in re.finditer(func_pattern, content, re.MULTILINE):
                line_num = content[:match.start()].count('\n') + 1
                structures.append({
                    'type': 'function',
                    'name': match.group(2),
                    'line': line_num,
                    'signature': match.group(1)
                })

            # Class pattern
            class_pattern = r'^(class\s+(\w+)(?:\([^)]*\))?:)'
            for match in re.finditer(class_pattern, content, re.MULTILINE):
                line_num = content[:match.start()].count('\n') + 1
                structures.append({
                    'type': 'class',
                    'name': match.group(2),
                    'line': line_num,
                    'signature': match.group(1)
                })

        elif ext in ['.js', '.jsx', '.ts', '.tsx']:
            # Extract JavaScript/TypeScript functions and classes
            # Function pattern (function declarations and arrow functions)
            func_patterns = [
                r'function\s+(\w+)\s*\([^)]*\)',
                r'const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>',
                r'(\w+)\s*:\s*(?:async\s*)?\([^)]*\)\s*=>',
            ]
            for pattern in func_patterns:
                for match in re.finditer(pattern, content):
                    line_num = content[:match.start()].count('\n') + 1
                    structures.append({
                        'type': 'function',
                        'name': match.group(1),
                        'line': line_num,
                        'signature': match.group(0)
                    })

            # Class pattern
            class_pattern = r'class\s+(\w+)(?:\s+extends\s+\w+)?'
            for match in re.finditer(class_pattern, content):
                line_num = content[:match.start()].count('\n') + 1
                structures.append({
                    'type': 'class',
                    'name': match.group(1),
                    'line': line_num,
                    'signature': match.group(0)
                })

        return structures

    def _chunk_file(self, content: str, file_info: Dict[str, Any],
                    structures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Chunk file content with overlap"""
        chunks = []
        lines = content.split('\n')

        # Try to chunk by logical units (functions/classes) first
        if structures:
            chunks.extend(self._chunk_by_structures(lines, file_info, structures))

        # Chunk any remaining content
        chunks.extend(self._chunk_by_lines(lines, file_info))

        return chunks

    def _chunk_by_structures(self, lines: List[str], file_info: Dict[str, Any],
                            structures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create chunks based on code structures (functions/classes)"""
        chunks = []

        for structure in structures:
            start_line = structure['line'] - 1
            # Find the end of this structure (heuristic: next structure or indentation change)
            end_line = min(start_line + 50, len(lines))  # Max 50 lines per structure

            chunk_lines = lines[start_line:end_line]
            chunk_content = '\n'.join(chunk_lines)

            if chunk_content.strip():
                chunks.append({
                    'content': chunk_content,
                    'file_path': file_info['path'],
                    'file_name': file_info['name'],
                    'chunk_type': 'structure',
                    'structure_type': structure['type'],
                    'structure_name': structure['name'],
                    'start_line': start_line + 1,
                    'end_line': end_line,
                    'metadata': {
                        'extension': file_info['extension'],
                        'signature': structure.get('signature', '')
                    }
                })

        return chunks

    def _chunk_by_lines(self, lines: List[str], file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create chunks based on line count"""
        chunks = []
        total_lines = len(lines)

        i = 0
        chunk_id = 0
        while i < total_lines:
            end_idx = min(i + self.chunk_size, total_lines)
            chunk_lines = lines[i:end_idx]
            chunk_content = '\n'.join(chunk_lines)

            if chunk_content.strip():
                chunks.append({
                    'content': chunk_content,
                    'file_path': file_info['path'],
                    'file_name': file_info['name'],
                    'chunk_type': 'sequential',
                    'start_line': i + 1,
                    'end_line': end_idx,
                    'chunk_id': chunk_id,
                    'metadata': {
                        'extension': file_info['extension']
                    }
                })
                chunk_id += 1

            # Move with overlap
            i += self.chunk_size - self.chunk_overlap

        return chunks
