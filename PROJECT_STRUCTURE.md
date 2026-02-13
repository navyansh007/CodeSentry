# CodeSentry Project Structure

```
CodeSentry/
│
├── codesentry/                    # Main package directory
│   ├── __init__.py               # Package initialization
│   ├── cli.py                    # CLI interface and orchestration
│   ├── static_analyzer.py        # Layer 1: Static analysis tools
│   ├── code_indexer.py           # Code chunking and indexing
│   ├── rag_system.py             # RAG with ChromaDB integration
│   ├── ai_reviewer.py            # Layer 2: AI-powered review
│   ├── report_generator.py       # HTML report generation
│   └── utils.py                  # Utility functions
│
├── reports/                       # Generated HTML reports (created at runtime)
│   └── code_review_*.html        # Timestamped review reports
│
├── .chroma_db/                   # ChromaDB storage (created at runtime)
│   └── [vector embeddings]       # Persistent vector database
│
├── config.yaml                   # Main configuration file
├── requirements.txt              # Python dependencies
├── setup.py                      # Package installation script
├── .gitignore                    # Git ignore patterns
├── .env.example                  # Environment variable template
│
├── README.md                     # Main documentation
├── QUICKSTART.md                 # Quick start guide
├── ARCHITECTURE.md               # Detailed architecture documentation
├── PROJECT_STRUCTURE.md          # This file
├── LICENSE                       # MIT License
│
├── Makefile                      # Convenience commands
└── example_usage.py              # Programmatic usage example
```

## File Descriptions

### Core Modules

#### `codesentry/cli.py`
- **Purpose**: Command-line interface and main orchestration
- **Key Functions**:
  - `main()`: CLI entry point with Click
  - `print_banner()`: Display CodeSentry banner
- **Dependencies**: click, colorama, all other modules

#### `codesentry/static_analyzer.py`
- **Purpose**: Static analysis layer (Pylint, Flake8, Bandit, Radon)
- **Key Class**: `StaticAnalyzer`
- **Methods**:
  - `analyze()`: Run all static analysis tools
  - `_run_pylint()`, `_run_flake8()`, etc.: Individual tool runners
  - `_generate_summary()`: Aggregate results

#### `codesentry/code_indexer.py`
- **Purpose**: Code chunking and structure extraction
- **Key Class**: `CodeIndexer`
- **Methods**:
  - `index_files()`: Process all files
  - `_extract_code_structures()`: Find functions/classes
  - `_chunk_file()`: Create code chunks
  - `_chunk_by_structures()`: Structure-based chunking
  - `_chunk_by_lines()`: Sequential chunking

#### `codesentry/rag_system.py`
- **Purpose**: RAG architecture with ChromaDB
- **Key Class**: `RAGSystem`
- **Methods**:
  - `index_chunks()`: Generate and store embeddings
  - `retrieve_context()`: Semantic search
  - `retrieve_file_context()`: File-specific retrieval
  - `retrieve_by_structure()`: Function/class retrieval
  - `get_diverse_samples()`: Sample across codebase

#### `codesentry/ai_reviewer.py`
- **Purpose**: AI-powered code review with LLM
- **Key Class**: `AIReviewer`
- **Methods**:
  - `perform_review()`: Run complete AI review
  - `_review_general_codebase()`: General overview
  - `_analyze_architecture()`: Architectural analysis
  - `_analyze_security()`: Security review
  - `_review_files()`: File-specific reviews
  - `_check_best_practices()`: Best practices check
  - `_generate_suggestions()`: Improvement suggestions
  - `_call_llm()`: API interface to Qwen3-Coder

#### `codesentry/report_generator.py`
- **Purpose**: HTML report generation
- **Key Class**: `ReportGenerator`
- **Methods**:
  - `generate_report()`: Create complete report
  - `_render_html()`: Render Jinja2 template
  - `_get_template()`: HTML template with embedded CSS

#### `codesentry/utils.py`
- **Purpose**: Common utility functions
- **Key Functions**:
  - `load_config()`: Load YAML configuration
  - `should_exclude()`: Check exclusion rules
  - `get_supported_files()`: Recursive file discovery
  - `get_file_language()`: Detect programming language
  - `ensure_dir()`: Create directories

### Configuration Files

#### `config.yaml`
- LLM configuration (API, model, parameters)
- ChromaDB settings (persistence, collection name)
- Embedding model configuration
- Static analysis tool settings
- RAG parameters (top-k, threshold)
- Report settings
- File exclusion rules

#### `requirements.txt`
```
chromadb==0.4.22              # Vector database
sentence-transformers==2.3.1   # Embedding model
requests==2.31.0               # HTTP requests for LLM API
pylint==3.0.3                  # Code quality
flake8==7.0.0                  # Style checking
autopep8==2.0.4                # Code formatting
radon==6.0.1                   # Complexity analysis
bandit==1.7.6                  # Security scanning
jinja2==3.1.3                  # HTML templating
click==8.1.7                   # CLI framework
colorama==0.4.6                # Terminal colors
tqdm==4.66.1                   # Progress bars
gitpython==3.1.41              # Git integration
```

#### `setup.py`
- Package metadata
- Dependencies
- Console script entry point: `codesentry`

### Documentation Files

#### `README.md`
- Main documentation
- Features overview
- Installation instructions
- Usage examples
- Configuration guide
- Troubleshooting

#### `QUICKSTART.md`
- Step-by-step quick start
- Minimal setup instructions
- First run example
- Common commands

#### `ARCHITECTURE.md`
- System architecture overview
- Design decisions
- Data flow diagrams
- Extension points
- Performance considerations

#### `PROJECT_STRUCTURE.md`
- This file
- Directory layout
- File descriptions

### Other Files

#### `Makefile`
Commands:
- `make install`: Install dependencies
- `make setup`: Create virtual environment
- `make clean`: Clean build artifacts
- `make run`: Run on current directory
- `make test`: Test on CodeSentry itself
- `make help`: Show help

#### `example_usage.py`
- Demonstrates programmatic API usage
- Can be used as a script template
- Shows how to integrate CodeSentry into other tools

#### `.env.example`
- Template for environment variables
- Shows required HF_TOKEN format
- Copy to `.env` and fill in

#### `.gitignore`
Excludes:
- Python cache (`__pycache__`, `*.pyc`)
- Build artifacts (`build/`, `dist/`, `*.egg-info`)
- Virtual environments (`venv/`, `env/`)
- ChromaDB storage (`.chroma_db/`)
- Generated reports (`reports/`)
- Environment files (`.env`)

## Runtime Generated Files

### `.chroma_db/`
- Created on first run
- Stores vector embeddings
- Persisted across runs
- Can be cleared with `--clear-cache`

### `reports/`
- Created automatically
- Contains HTML reports
- Filename format: `code_review_YYYYMMDD_HHMMSS.html`
- Each report is self-contained

## Package Installation

After `pip install -e .`, the following is installed:

```
Site-packages/
└── codesentry.egg-link  → points to source directory

Scripts/
└── codesentry           → CLI entry point
```

## Import Structure

```python
# Typical import patterns
from codesentry.utils import load_config
from codesentry.static_analyzer import StaticAnalyzer
from codesentry.rag_system import RAGSystem
from codesentry.ai_reviewer import AIReviewer
from codesentry.report_generator import ReportGenerator
```

## Entry Points

### CLI Entry Point
```bash
codesentry [OPTIONS]
```
→ Calls `codesentry.cli:main()`

### Programmatic Entry Point
```python
from codesentry.cli import main
main()
```

### Custom Integration
```python
from codesentry.utils import load_config, get_supported_files
from codesentry.static_analyzer import StaticAnalyzer
# ... use individual components
```

## Development Workflow

1. **Setup**: `make setup && make install`
2. **Edit**: Modify files in `codesentry/`
3. **Test**: `make test` (runs on itself)
4. **Run**: `codesentry --path <target>`
5. **Clean**: `make clean` (remove artifacts)

## Adding New Features

### New Static Analyzer
1. Edit `codesentry/static_analyzer.py`
2. Add `_run_<tool>()` method
3. Update `analyze()` to call it
4. Update `config.yaml` with tool settings

### New AI Review Type
1. Edit `codesentry/ai_reviewer.py`
2. Add method (e.g., `_analyze_<aspect>()`)
3. Call from `perform_review()`
4. Update report template to display results

### New Report Section
1. Edit `codesentry/report_generator.py`
2. Modify `_get_template()` HTML
3. Pass new data in `template.render()`
4. Add CSS styling if needed

## File Size Estimates

```
codesentry/
├── cli.py                 ~6 KB
├── static_analyzer.py     ~8 KB
├── code_indexer.py        ~10 KB
├── rag_system.py          ~8 KB
├── ai_reviewer.py         ~12 KB
├── report_generator.py    ~18 KB (large HTML template)
└── utils.py               ~3 KB

Total package: ~65 KB

Documentation: ~50 KB
Configuration: ~5 KB

Generated reports: 200-500 KB each (depending on project size)
ChromaDB storage: Varies (depends on codebase size)
```

## Dependencies Graph

```
cli.py
 ├─→ utils.py
 ├─→ static_analyzer.py
 ├─→ code_indexer.py
 │    └─→ utils.py
 ├─→ rag_system.py
 │    └─→ sentence_transformers
 │    └─→ chromadb
 ├─→ ai_reviewer.py
 │    ├─→ rag_system.py
 │    └─→ requests (Hugging Face API)
 └─→ report_generator.py
      └─→ jinja2
```

## Minimal Installation

For users who only want static analysis (no AI):

```txt
pylint==3.0.3
flake8==7.0.0
bandit==1.7.6
radon==6.0.1
jinja2==3.1.3
click==8.1.7
colorama==0.4.6
pyyaml>=5.0
```

Use with: `codesentry --no-ai`

## Summary

- **Total Python Files**: 8 (in `codesentry/`)
- **Total Documentation**: 5 markdown files
- **Configuration Files**: 4
- **Total Lines of Code**: ~2,500
- **External Dependencies**: 13 packages
- **Supported Languages**: 10+ (for AI review), Python (for static)
