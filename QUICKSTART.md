# 🚀 Quick Start Guide

Get CodeSentry up and running in 5 minutes!

## Step 1: Installation

```bash
# Navigate to CodeSentry directory
cd /path/to/CodeSentry

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install CodeSentry
pip install -e .
```

## Step 2: Set Up API Token

1. Get a Hugging Face token from https://huggingface.co/settings/tokens
2. Export it as an environment variable:

```bash
export HF_TOKEN="your_token_here"
```

Or create a `.env` file:
```bash
cp .env.example .env
# Edit .env and add your token
```

## Step 3: Run Your First Review

```bash
# Review current directory
codesentry

# Or review a specific project
codesentry --path /path/to/your/project
```

## Step 4: View Results

The HTML report will be generated in the `reports/` directory. Open it in your browser:

```bash
# On macOS
open reports/code_review_*.html

# On Linux
xdg-open reports/code_review_*.html

# On Windows
start reports/code_review_*.html
```

## What to Expect

CodeSentry will:
1. ✅ Scan your codebase for supported files
2. ✅ Run static analysis (Pylint, Flake8, Bandit, Radon)
3. ✅ Index your code into ChromaDB with embeddings
4. ✅ Perform AI-powered review using Qwen3-Coder LLM
5. ✅ Generate a beautiful HTML report

## Example Output

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   🛡️  CodeSentry - AI-Powered Code Review System             ║
║                                                               ║
║   Static Analysis + AI Review with RAG Architecture          ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

Loading configuration...
✓ Configuration loaded
Analyzing codebase: /path/to/your/project

Scanning for files...
✓ Found 25 files to analyze

============================================================
LAYER 1: STATIC ANALYSIS
============================================================

Running static analysis on 15 Python files...
  Running Pylint...
  Running Flake8...
  Running Bandit (security)...
  Running Radon (complexity)...

✓ Static analysis complete
  Total issues found: 42

============================================================
LAYER 2: AI-POWERED REVIEW WITH RAG
============================================================

Step 1: Indexing codebase...
Indexing 25 files...
Created 156 code chunks
✓ Code indexing complete

Step 2: Setting up RAG system...
Initializing RAG system with sentence-transformers/all-MiniLM-L6-v2...
Indexing 156 chunks into ChromaDB...
  Generating embeddings...
  Successfully indexed 156 chunks
✓ RAG system ready

Step 3: Performing AI review...
  Generating general codebase review...
  Analyzing architecture...
  Analyzing security concerns...
  Reviewing individual files...
  Checking best practices...
  Generating improvement suggestions...

✓ AI review complete

============================================================
GENERATING REPORT
============================================================

Generating HTML report...
Report generated: reports/code_review_20250116_143022.html

============================================================
✓ REVIEW COMPLETE
============================================================

Report saved to: reports/code_review_20250116_143022.html

Open the report in your browser to view detailed results.
```

## Tips for Best Results

1. **Set HF_TOKEN**: AI review requires a valid Hugging Face token
2. **Review Regularly**: Run CodeSentry during development to catch issues early
3. **Customize Config**: Edit `config.yaml` to adjust analysis parameters
4. **Focus on Priorities**: Start with security issues and errors
5. **Iterative Improvement**: Address issues incrementally

## Common Commands

```bash
# Review with clean cache (recommended for first run)
codesentry --clear-cache

# Static analysis only (faster, no API calls)
codesentry --no-ai

# AI review only (skip linting)
codesentry --no-static

# Custom output directory
codesentry --output ./my-reports

# Help
codesentry --help
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Customize `config.yaml` for your project needs
- Integrate CodeSentry into your development workflow
- Set up CI/CD integration for automated reviews

Happy coding! 🎉
