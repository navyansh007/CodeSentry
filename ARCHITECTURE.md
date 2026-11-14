# CodeSentry Architecture

This document provides a detailed overview of CodeSentry's architecture, design decisions, and implementation details.

## System Overview

CodeSentry is built as a modular, two-layer code review system that combines traditional static analysis with modern AI-powered code understanding using RAG (Retrieval-Augmented Generation) architecture.

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Interface                         │
│                      (cli.py)                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌──────────────┐            ┌──────────────────┐
│   Layer 1    │            │     Layer 2      │
│    Static    │            │   AI-Powered     │
│   Analysis   │            │   Review (RAG)   │
└──────┬───────┘            └────────┬─────────┘
       │                             │
       │    ┌────────────────────────┤
       │    │                        │
       ▼    ▼                        ▼
┌──────────────────────────────────────────┐
│          Report Generator                 │
│         (HTML Output)                     │
└──────────────────────────────────────────┘
```

## Module Architecture

### 1. CLI Interface (`cli.py`)

**Responsibility**: User interaction, orchestration, and workflow management

**Key Features**:
- Command-line argument parsing using Click
- Configuration loading and validation
- Colorized terminal output (colorama)
- Progress tracking and user feedback
- Error handling and graceful degradation

**Flow**:
1. Parse command-line arguments
2. Load and validate configuration
3. Discover files for analysis
4. Execute Layer 1 (Static Analysis)
5. Execute Layer 2 (AI Review with RAG)
6. Generate and save report

### 2. Static Analysis Layer (`static_analyzer.py`)

**Responsibility**: Conventional code quality and security checks

**Components**:

#### Pylint Integration
- Code quality analysis
- Style guide enforcement
- Error detection
- JSON output parsing

#### Flake8 Integration
- PEP 8 compliance checking
- Pattern-based issue detection
- Text output parsing

#### Bandit Integration
- Security vulnerability scanning
- Common security anti-patterns
- Severity classification
- JSON output processing

#### Radon Integration
- Cyclomatic complexity analysis
- Maintainability index
- Function-level metrics

**Output**: Structured dictionary with:
- Issue lists per tool
- Summary statistics
- Severity breakdowns

### 3. Code Indexer (`code_indexer.py`)

**Responsibility**: Transform source code into analyzable chunks

**Chunking Strategies**:

#### Structure-Based Chunking
- Extracts functions and classes using regex patterns
- Language-aware parsing (Python, JavaScript/TypeScript)
- Preserves code structure and context
- Metadata: function/class names, signatures, line numbers

#### Sequential Chunking
- Line-based chunking with configurable size and overlap
- Fallback for code without clear structure
- Ensures complete coverage

**Chunk Metadata**:
```python
{
    'content': str,           # Code content
    'file_path': str,         # Source file path
    'file_name': str,         # File name
    'chunk_type': str,        # 'structure' or 'sequential'
    'start_line': int,        # Starting line number
    'end_line': int,          # Ending line number
    'structure_type': str,    # 'function', 'class', etc. (optional)
    'structure_name': str,    # Name of function/class (optional)
    'metadata': dict          # Additional metadata
}
```

### 4. RAG System (`rag_system.py`)

**Responsibility**: Semantic code search and context retrieval

**Architecture**:

```
┌─────────────────┐
│  Code Chunks    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Sentence        │
│ Transformers    │
│ (Embeddings)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   ChromaDB      │
│ (Vector Store)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Similarity      │
│ Search          │
└─────────────────┘
```

**Components**:

#### Embedding Model
- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Converts code to 384-dimensional vectors
- Fast inference, good semantic understanding
- Batch processing for efficiency

#### ChromaDB Vector Database
- Persistent storage of embeddings
- Fast cosine similarity search
- Metadata filtering capabilities
- Collection management

**Retrieval Methods**:

1. **Semantic Search** (`retrieve_context`)
   - Query-based similarity search
   - Top-K results with threshold filtering
   - Returns ranked chunks by relevance

2. **File-Based Retrieval** (`retrieve_file_context`)
   - Get all chunks for specific files
   - Useful for file-specific reviews

3. **Structure-Based Retrieval** (`retrieve_by_structure`)
   - Find specific functions/classes
   - Supports targeted analysis

4. **Diverse Sampling** (`get_diverse_samples`)
   - Sample across different files
   - Provides broad codebase overview

### 5. AI Reviewer (`ai_reviewer.py`)

**Responsibility**: LLM-powered code analysis using RAG

**Review Pipeline**:

```
┌──────────────┐
│  Query       │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ RAG System   │
│ (Context     │
│  Retrieval)  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Prompt       │
│ Construction │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Qwen3-Coder  │
│ LLM API      │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Response     │
│ Processing   │
└──────────────┘
```

**Analysis Types**:

1. **General Codebase Review**
   - Uses diverse code samples
   - Provides high-level overview
   - Identifies patterns and anti-patterns

2. **Architectural Analysis**
   - Analyzes file structure
   - Evaluates modularity and organization
   - Suggests improvements

3. **Security Analysis**
   - Augments Bandit findings with AI insights
   - Provides context-aware security recommendations
   - Assesses severity and impact

4. **File-Specific Reviews**
   - Deep dive into individual files
   - Code quality, bugs, performance
   - Actionable suggestions

5. **Best Practices Check**
   - Coding standards compliance
   - Documentation quality
   - Error handling patterns

6. **Improvement Suggestions**
   - Synthesizes all findings
   - Prioritized recommendations
   - Based on static analysis metrics

**LLM Integration**:
- API: Hugging Face Inference API
- Model: Qwen/Qwen3-Coder-30B-A3B-Instruct
- Temperature: 0.3 (focused, deterministic)
- Max tokens: 2000
- Timeout: 60 seconds

### 6. Report Generator (`report_generator.py`)

**Responsibility**: Create comprehensive HTML reports

**Features**:

- **Jinja2 Templating**: Flexible, maintainable templates
- **Responsive Design**: Mobile-friendly layout
- **Color Coding**: Visual severity indicators
- **Section Organization**: Logical information hierarchy
- **Print-Friendly**: Optimized for PDF export

**Report Sections**:

1. Header: Project info, analysis metadata
2. Summary: Key metrics and statistics
3. AI Analysis: General review and architectural insights
4. Security: Detailed security findings
5. Static Analysis: Tool-specific issue lists
6. File Reviews: Per-file AI assessments
7. Best Practices: Standards compliance
8. Suggestions: Prioritized improvements

**Styling**:
- Gradient headers
- Card-based layout
- Syntax-highlighted code blocks
- Badge system for severity
- Grid layouts for responsiveness

### 7. Utilities (`utils.py`)

**Responsibility**: Common helper functions

**Functions**:

- `load_config()`: YAML configuration loading
- `should_exclude()`: File/directory exclusion logic
- `get_supported_files()`: Recursive file discovery
- `get_file_language()`: Language detection
- `ensure_dir()`: Directory creation helper

### 8. Guardrail Pipeline (`triage.py`, `guardrails.py`, `findings.py`, `critic.py`)

**Responsibility**: Keep AI review precise, cheap, and resistant to manipulation

```
file ──► InputGuardrails ──► ReviewTriage ──► LLM review ──► OutputGuardrails ──► FindingCritic ──► findings
         (redact secrets,   (skip generated/  (structured   (grounding, conf.,  (refute-only,
          flag injection)    trivial/clean,    JSON findings) nitpick, dedupe,    sees code + claim,
                             rank by risk)                    diff scope, caps)   not reasoning)
```

- Deterministic findings (secrets, injection attempts, linter issues) carry a `guardrail:` or `static:` source. They skip the confidence/evidence filters and the critic, which exist to catch LLM errors.
- Every dropped finding is recorded with a reason and reported, so suppression is never silent.
- The critic fails open: if it can't answer, findings are kept and marked `UNCERTAIN`.

### 9. GitHub PR Review (`pr_reviewer.py`, `github_client.py`, `diff_utils.py`, `github_cli.py`)

**Responsibility**: Review a pull request and post inline comments

**Flow**:
1. Fetch the PR, its changed files and patches, and each file at the head SHA
2. `parse_patch()` maps each patch to added and context line numbers
3. Static analysis on the materialized files; only issues on added lines count
4. `detect_security_regressions()` runs on the diff alone; the PR narrative never reaches the LLM
5. Triage and AI review focused on added lines (large files are sent as windows around them)
6. Output guardrails scoped to added lines, then the critic
7. Fingerprinted inline comments are skipped if already posted; the summary comment is upserted by marker

## Data Flow

### Complete Analysis Flow

```
1. CLI Initialization
   ├─> Load config.yaml
   ├─> Parse arguments
   └─> Validate HF_TOKEN

2. File Discovery
   ├─> Walk directory tree
   ├─> Apply exclusion rules
   └─> Filter by extensions

3. Static Analysis (Layer 1)
   ├─> Run Pylint → JSON results
   ├─> Run Flake8 → Text parsing
   ├─> Run Bandit → JSON results
   ├─> Run Radon → JSON results
   └─> Aggregate → Summary stats

4. Code Indexing
   ├─> Read files
   ├─> Extract structures (functions/classes)
   ├─> Create chunks (structure + sequential)
   └─> Generate metadata

5. RAG System Setup
   ├─> Load embedding model
   ├─> Initialize ChromaDB
   ├─> Generate embeddings (batched)
   └─> Store in vector database

6. AI Review (Layer 2)
   ├─> General Review
   │   ├─> Sample diverse chunks
   │   ├─> Build context
   │   └─> Query LLM
   │
   ├─> Architecture Analysis
   │   ├─> Analyze file structure
   │   └─> Query LLM
   │
   ├─> Security Analysis
   │   ├─> Get Bandit issues
   │   ├─> Retrieve relevant code (RAG)
   │   └─> Query LLM per issue
   │
   ├─> File Reviews
   │   ├─> Retrieve file chunks (RAG)
   │   └─> Query LLM per file
   │
   ├─> Best Practices
   │   ├─> Sample code chunks
   │   └─> Query LLM
   │
   └─> Suggestions
       ├─> Analyze static results
       └─> Query LLM

7. Report Generation
   ├─> Render Jinja2 template
   ├─> Inject data (static + AI results)
   ├─> Apply styling
   └─> Write HTML file

8. Output
   └─> Display report path
```

## Design Decisions

### Why RAG?

**Problem**: LLMs have limited context windows and no knowledge of your specific codebase.

**Solution**: RAG provides relevant code context to the LLM:
- Only relevant chunks are sent (reduces tokens)
- Semantic search finds related code
- LLM gets focused, contextual information
- Better accuracy and relevance

### Why ChromaDB?

- **Simple API**: Easy integration
- **Persistent Storage**: Reuse embeddings across runs
- **Fast Similarity Search**: Optimized for vector operations
- **Metadata Filtering**: Flexible querying
- **No Server Required**: Embedded database

### Why Sentence Transformers?

- **Code Understanding**: Trained on diverse text, works well for code
- **Fast**: Efficient inference
- **Offline**: No API calls needed
- **Quality**: Good semantic similarity for code

### Why Two Layers?

**Layer 1 (Static)**:
- Fast, deterministic
- No API costs
- Catches common issues
- Provides metrics for AI layer

**Layer 2 (AI)**:
- Context-aware insights
- Human-like reasoning
- Novel issue detection
- Architectural understanding

**Together**: Comprehensive coverage, both breadth and depth

## Configuration

### Key Parameters

**Chunking**:
- `chunk_size: 500`: Balance between context and granularity
- `chunk_overlap: 50`: Ensures continuity across chunks

**RAG**:
- `top_k_results: 5`: Enough context without overwhelming LLM
- `similarity_threshold: 0.7`: Filter low-relevance results

**LLM**:
- `temperature: 0.3`: Focused, consistent responses
- `max_tokens: 2000`: Detailed but constrained output

## Performance Considerations

### Optimization Strategies

1. **Batch Processing**: Embeddings generated in batches
2. **Caching**: ChromaDB persists embeddings
3. **Parallel Analysis**: Independent tools run concurrently
4. **Lazy Loading**: Only load what's needed
5. **Timeout Protection**: Prevents hanging on large files

### Scalability

- **Small Projects** (< 50 files): ~2-5 minutes
- **Medium Projects** (50-200 files): ~5-15 minutes
- **Large Projects** (> 200 files): ~15-30 minutes

Bottlenecks:
- LLM API calls (dominant factor)
- Embedding generation (one-time cost)
- Static analysis (depends on code quality)

## Extension Points

### Adding New Static Analyzers

1. Create method in `StaticAnalyzer`
2. Add configuration in `config.yaml`
3. Parse output format
4. Update summary generation

### Supporting New Languages

1. Add extension to `config.yaml`
2. Update `_extract_code_structures()` in `code_indexer.py`
3. Add language-specific patterns

### Custom Report Sections

1. Modify HTML template in `report_generator.py`
2. Add data processing in `ReportGenerator`
3. Update CSS styling

### Alternative LLMs

1. Modify `_call_llm()` in `ai_reviewer.py`
2. Update API endpoint and payload format
3. Adjust configuration parameters

## Security Considerations

- **API Key Protection**: HF_TOKEN via environment variable
- **Input Validation**: File path sanitization
- **Timeout Protection**: Prevents DoS via large files
- **No Code Execution**: Static analysis only (except Pylint/Bandit)
- **Output Sanitization**: HTML escaping in reports
- **Secret Redaction**: credentials are masked before any code is sent to an LLM provider
- **Prompt-Injection Resistance**: repository content is fenced as untrusted data, instructions aimed at AI reviewers are flagged, and PR descriptions are never sent to the LLM
- **PR Code Is Never Executed**: the GitHub Action fetches files through the API and only analyzes them statically

## Future Enhancements

- [x] Incremental analysis (only changed files)
- [x] CI/CD integration plugins (GitHub Action)
- [x] Custom rule definitions
- [x] Multi-LLM support
- [ ] Multi-model consensus for the critic
- [ ] Interactive web UI
- [ ] Code fix suggestions (with diffs)
- [ ] Trend analysis across commits
- [ ] Team collaboration features

## Conclusion

CodeSentry's architecture balances:
- **Simplicity**: Easy to understand and extend
- **Power**: Advanced AI capabilities with RAG
- **Flexibility**: Configurable, modular design
- **Performance**: Optimized for practical use

The two-layer approach ensures comprehensive coverage while the RAG architecture enables context-aware AI analysis that understands your specific codebase.
