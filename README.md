# CodeSentry

**AI-powered code review with static analysis and RAG**

CodeSentry is a CLI tool that reviews code in two passes: a static analysis layer using standard linting tools, and an AI layer backed by Qwen3-Coder with RAG (Retrieval-Augmented Generation) for context-aware feedback.

## Demo

[![CodeSentry Demo](https://img.youtube.com/vi/S0Pihfd9CM0/maxresdefault.jpg)](https://youtu.be/S0Pihfd9CM0)

## Features

### Static analysis
- **Pylint** — code quality and style
- **Flake8** — PEP 8 compliance
- **Bandit** — security vulnerability detection
- **Radon** — cyclomatic complexity

### AI review
- ChromaDB-backed vector store for code context retrieval
- Semantic chunking with function/class awareness
- Qwen3-Coder-30B for the actual review
- Covers: general overview, architecture, security, per-file review, best practices, and improvement suggestions

### Reports
- HTML output with charts and an issue breakdown table
- Color-coded by severity
- Metrics from both layers in one place

## Prerequisites

- Python 3.8+
- Hugging Face account with API token ([get one here](https://huggingface.co/settings/tokens))

## Installation

### 1. Clone or download CodeSentry

```bash
cd /path/to/CodeSentry
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install CodeSentry

```bash
pip install -e .
```

### 5. Set your Hugging Face token

```bash
export HF_TOKEN="your_huggingface_token_here"
```

Or add it permanently to your shell profile:

```bash
echo 'export HF_TOKEN="your_huggingface_token_here"' >> ~/.bashrc
source ~/.bashrc
```

## Usage

### Basic usage

Review the current directory:
```bash
codesentry
```

Review a specific directory:
```bash
codesentry --path /path/to/your/project
```

### Options

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

# Only analyze files changed since last commit
codesentry --diff

# Diff against a specific branch
codesentry --diff --base-ref main
```

### All command-line options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--path` | `-p` | Path to codebase directory | `.` |
| `--config` | `-c` | Path to configuration file | `config.yaml` |
| `--output` | `-o` | Output directory for reports | `reports/` |
| `--no-static` | | Skip static analysis | False |
| `--no-ai` | | Skip AI review | False |
| `--clear-cache` | | Clear ChromaDB cache | False |
| `--diff` | | Only analyze git-changed files | False |
| `--base-ref` | | Git ref to diff against (used with `--diff`) | `HEAD` |

## Configuration

Edit `config.yaml` to adjust behavior:

```yaml
# LLM configuration
llm:
  api_url: "https://router.huggingface.ro/v1/chat/completions"
  model: "Qwen/Qwen3-Coder-30B-A3B-Instruct:scaleway"
  max_tokens: 2000
  temperature: 0.3

# ChromaDB configuration
chromadb:
  persist_directory: ".chroma_db"
  collection_name: "code_embeddings"

# Embedding model
embeddings:
  model_name: "sentence-transformers/all-MiniLM-L6-v2"
  chunk_size: 500
  chunk_overlap: 50

# RAG settings
rag:
  top_k_results: 5
  similarity_threshold: 0.7

# File extensions to analyze
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

## Understanding the report

Reports land in the `reports/` directory as HTML files.

### Sections

1. **Analysis summary** — high-level stats with color-coded metrics
2. **AI analysis** — general codebase review and architectural notes
3. **Security analysis** — vulnerability assessments from Bandit and the AI layer
4. **Static analysis results** — issues from Pylint, Flake8, Bandit, and Radon
5. **File-specific reviews** — per-file AI review (first 5 files by default)
6. **Best practices** — adherence to coding standards
7. **Improvement suggestions** — prioritized action items

### Severity levels

- **Error** — critical issues, fix immediately
- **Warning** — should be addressed
- **Info** — suggestions and notes
- **Security** — vulnerabilities flagged by Bandit

## How it works

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

### RAG

Code is chunked and embedded with sentence-transformers, stored in ChromaDB. When reviewing, the most relevant chunks are retrieved and stuffed into the LLM prompt. That way the model actually sees related code from elsewhere in the repo, not just whatever's in the immediate file.

## Supported languages

Static analysis tools cover Python only. The AI layer handles:
- Python (.py)
- JavaScript (.js, .jsx)
- TypeScript (.ts, .tsx)
- Java (.java)
- C/C++ (.c, .cpp)
- Go (.go)
- Ruby (.rb)
- PHP (.php)

## Contributing

PRs welcome. Static analysis beyond Python (ESLint, golint, etc.) would be a good starting point, as would a plugin system for custom analyzers. CI/CD integration improvements are also useful — the current example is pretty bare.

## Examples

### Quick review

```bash
cd ~/my-project
codesentry
open reports/code_review_*.html
```

### Large project with custom config

```bash
cp config.yaml my-config.yaml
# Edit my-config.yaml to adjust settings

codesentry --path ~/large-project --config my-config.yaml --clear-cache
```

### CI/CD integration

```bash
#!/bin/bash
# ci-review.sh

export HF_TOKEN="${HUGGINGFACE_TOKEN}"

codesentry \
  --path . \
  --output ./review-reports \
  --no-ai  # static analysis only for faster CI runs

if [ $? -ne 0 ]; then
  echo "Code review found critical issues"
  exit 1
fi
```

### Review only changed files (useful for PR checks)

```bash
codesentry --diff --base-ref main
```

## Troubleshooting

**"HF_TOKEN not set"** — export your token before running:
```bash
export HF_TOKEN="your_token_here"
```

**ChromaDB permission errors** — check write permissions in the directory where `.chroma_db` is created.

**Timeouts on large codebases** — use `--no-ai` for a faster run, or increase timeout values in `config.yaml`.

**No Python files found** — if the project has no Python, use `--no-static` to skip static analysis.

## License

Provided as-is for educational and professional use.

## Acknowledgments

- [Qwen3-Coder](https://huggingface.co/Qwen) by Alibaba Cloud
- [ChromaDB](https://www.trychroma.com/)
- [Sentence Transformers](https://www.sbert.net/)
- Pylint, Flake8, Bandit, Radon
