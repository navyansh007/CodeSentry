# 🛡️ CodeSentry

**AI-Powered Code Review System with Static Analysis and RAG Architecture**

CodeSentry is a comprehensive command-line tool that performs detailed code reviews using a two-layer approach:
1. **Static Analysis Layer**: Conventional linting and security checks using industry-standard tools
2. **AI Review Layer**: Advanced code review using Qwen3-Coder LLM with RAG (Retrieval-Augmented Generation) architecture

## ✨ Features

### Static Analysis Layer
- **Pylint**: Code quality and style analysis
- **Flake8**: PEP 8 style guide enforcement
- **Bandit**: Security vulnerability detection
- **Radon**: Code complexity analysis

### AI Review Layer
- **RAG Architecture**: Uses ChromaDB for intelligent code context retrieval
- **Advanced Code Indexing**: Semantic chunking of code with function/class awareness
- **LLM-Powered Review**: Leverages Qwen3-Coder-30B for deep code analysis
- **Multi-faceted Analysis**:
  - General codebase overview
  - Architectural insights
  - Security concern analysis
  - File-specific reviews
  - Best practices validation
  - Actionable improvement suggestions

### Report Generation
- Beautiful, detailed HTML reports
- Interactive visualizations
- Color-coded issue severity
- Comprehensive metrics and statistics
- Print-friendly format

## 📋 Prerequisites

- Python 3.8 or higher
- Hugging Face account with API token ([Get one here](https://huggingface.co/settings/tokens))

## 🚀 Installation

### 1. Clone or Download CodeSentry

```bash
cd /path/to/CodeSentry
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install CodeSentry

```bash
pip install -e .
```

### 5. Set Up Hugging Face Token

Export your Hugging Face token as an environment variable:

```bash
export HF_TOKEN="your_huggingface_token_here"
```

Or add it to your shell profile (~/.bashrc, ~/.zshrc, etc.):

```bash
echo 'export HF_TOKEN="your_huggingface_token_here"' >> ~/.bashrc
source ~/.bashrc
```

## 📖 Usage

### Basic Usage

Review the current directory:
```bash
codesentry
```

Review a specific directory:
```bash
codesentry --path /path/to/your/project
```

### Advanced Options

```bash
# Skip static analysis (AI review only)
codesentry --path ./my-project --no-static

# Skip AI review (static analysis only)
codesentry --path ./my-project --no-ai

# Specify custom output directory
codesentry --path ./my-project --output ./custom-reports

# Use custom configuration file
codesentry --path ./my-project --config ./my-config.yaml

# Clear ChromaDB cache before analysis
codesentry --path ./my-project --clear-cache
```

### Command-Line Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--path` | `-p` | Path to codebase directory | Current directory (`.`) |
| `--config` | `-c` | Path to configuration file | `config.yaml` |
| `--output` | `-o` | Output directory for reports | `reports/` |
| `--no-static` | | Skip static analysis layer | False |
| `--no-ai` | | Skip AI review layer | False |
| `--clear-cache` | | Clear ChromaDB cache | False |

## ⚙️ Configuration

Edit `config.yaml` to customize CodeSentry's behavior:

```yaml
# LLM Configuration
llm:
  api_url: "https://router.huggingface.ro/v1/chat/completions"
  model: "Qwen/Qwen3-Coder-30B-A3B-Instruct:scaleway"
  max_tokens: 2000
  temperature: 0.3

# ChromaDB Configuration
chromadb:
  persist_directory: ".chroma_db"
  collection_name: "code_embeddings"

# Embedding Model
embeddings:
  model_name: "sentence-transformers/all-MiniLM-L6-v2"
  chunk_size: 500
  chunk_overlap: 50

# RAG Settings
rag:
  top_k_results: 5
  similarity_threshold: 0.7

# File Extensions to Analyze
static_analysis:
  file_extensions:
    - .py
    - .js
    - .ts
    - .jsx
    - .tsx
    - .java
    - .cpp
    - .c
    - .go
    - .rb
    - .php

# Exclusions
exclude:
  directories:
    - node_modules
    - venv
    - .git
    - __pycache__
    - build
    - dist
```

## 📊 Understanding the Report

After running CodeSentry, an HTML report will be generated in the `reports/` directory.

### Report Sections

1. **Analysis Summary**: High-level statistics with color-coded metrics
2. **AI-Powered Analysis**: General codebase review and architectural insights
3. **Security Analysis**: Detailed security vulnerability assessments
4. **Static Analysis Results**: Issues found by Pylint, Flake8, Bandit, and Radon
5. **File-Specific Reviews**: AI reviews of individual files
6. **Best Practices Check**: Adherence to coding standards
7. **Improvement Suggestions**: Prioritized action items

### Severity Levels

- 🔴 **Error**: Critical issues requiring immediate attention
- 🟡 **Warning**: Important issues that should be addressed
- 🔵 **Info**: Informational items and suggestions
- 🔒 **Security**: Security vulnerabilities and concerns

## 🔧 How It Works

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   CodeSentry CLI                        │
└────────────────┬────────────────────────────────────────┘
                 │
                 ├──► LAYER 1: Static Analysis
                 │    ├── Pylint (code quality)
                 │    ├── Flake8 (style)
                 │    ├── Bandit (security)
                 │    └── Radon (complexity)
                 │
                 ├──► LAYER 2: AI Review with RAG
                 │    ├── Code Indexer
                 │    │   └── Semantic chunking
                 │    │
                 │    ├── ChromaDB
                 │    │   └── Vector embeddings
                 │    │
                 │    ├── RAG System
                 │    │   └── Context retrieval
                 │    │
                 │    └── Qwen3-Coder LLM
                 │        └── AI-powered review
                 │
                 └──► Report Generator
                      └── HTML report with visualizations
```

### RAG (Retrieval-Augmented Generation)

CodeSentry uses RAG to provide the LLM with relevant code context:

1. **Indexing**: Code is semantically chunked and embedded using sentence-transformers
2. **Storage**: Embeddings are stored in ChromaDB for fast similarity search
3. **Retrieval**: When analyzing, relevant code chunks are retrieved based on similarity
4. **Augmentation**: Retrieved context is added to LLM prompts for informed analysis
5. **Generation**: LLM generates insights based on both the query and retrieved context

This approach allows the LLM to understand code relationships and provide more accurate, context-aware reviews.

## 🎯 Supported Languages

Currently, static analysis tools focus on Python, but the AI layer can analyze:
- Python (.py)
- JavaScript (.js, .jsx)
- TypeScript (.ts, .tsx)
- Java (.java)
- C/C++ (.c, .cpp)
- Go (.go)
- Ruby (.rb)
- PHP (.php)
- And more!

## 🤝 Contributing

Contributions are welcome! Areas for improvement:
- Additional static analysis tools
- Support for more programming languages
- Custom rule definitions
- Integration with CI/CD pipelines
- Plugin system for custom analyzers

## 📝 Examples

### Example 1: Quick Review

```bash
# Navigate to your project
cd ~/my-project

# Run CodeSentry
codesentry

# Open the generated report
open reports/code_review_*.html
```

### Example 2: Large Project with Custom Config

```bash
# Create custom configuration
cp config.yaml my-config.yaml
# Edit my-config.yaml to adjust settings

# Run with custom config
codesentry --path ~/large-project --config my-config.yaml --clear-cache
```

### Example 3: CI/CD Integration

```bash
#!/bin/bash
# ci-review.sh

export HF_TOKEN="${HUGGINGFACE_TOKEN}"

codesentry \
  --path . \
  --output ./review-reports \
  --no-ai  # Use static analysis only for faster CI runs

# Check exit code
if [ $? -ne 0 ]; then
  echo "Code review found critical issues"
  exit 1
fi
```

## 🐛 Troubleshooting

### "HF_TOKEN not set" Warning
Make sure you've exported your Hugging Face token:
```bash
export HF_TOKEN="your_token_here"
```

### ChromaDB Permission Errors
Ensure you have write permissions in the directory where `.chroma_db` is created.

### Timeout Errors
For large codebases, increase timeout values in the configuration or use `--no-ai` for faster analysis.

### No Python Files Found
CodeSentry currently requires Python files for static analysis. Use `--no-static` if analyzing non-Python projects.

## 📄 License

This project is provided as-is for educational and professional use.

## 🙏 Acknowledgments

- **Qwen3-Coder**: Advanced code LLM from Alibaba Cloud
- **ChromaDB**: Vector database for embeddings
- **Sentence Transformers**: Embedding models
- **Pylint, Flake8, Bandit, Radon**: Static analysis tools

## 📧 Support

For issues, questions, or contributions, please open an issue in the project repository.

---

**Built with ❤️ for better code quality**
