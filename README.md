# CodeSentry

**AI-powered code review with static analysis and RAG**

CodeSentry is a CLI tool that reviews code in two passes: a static analysis layer covering multiple languages, and an AI layer backed by any LLM provider you configure, with RAG (Retrieval-Augmented Generation) for context-aware feedback. Every review also produces a single 0-100 quality score, which a configurable rule engine can use to pass/fail your CI.

## Demo

[![CodeSentry Demo](https://img.youtube.com/vi/utunWzmwfRo/maxresdefault.jpg)](https://youtu.be/utunWzmwfRo)

## Features

### Static analysis (multi-language)
Each language runs whichever of its tools you have installed; missing tools are skipped with a message rather than failing the run.

| Language | Tools |
|---|---|
| Python | Pylint, Flake8, Bandit (security), Radon (complexity) |
| JavaScript / TypeScript | ESLint |
| Go | gofmt, go vet, staticcheck (optional) |
| Rust | cargo clippy |
| Ruby | RuboCop |
| PHP | `php -l` |
| Java | Checkstyle (optional) |
| C / C++ | cppcheck |

Every tool's output is normalized into a common issue shape (file, line, severity, message) so results stay consistent across every language, not just Python.

### AI review — bring your own LLM provider
- Works with any commercial or open-source LLM provider: **OpenAI, Anthropic Claude, Google Gemini, Azure OpenAI, Hugging Face, Ollama (local/offline), OpenRouter, Groq, Together, Mistral, DeepSeek**, or any other OpenAI-compatible endpoint (vLLM, LocalAI, LM Studio, ...)
- Configured entirely in `config.yaml` — swap providers/models with no code changes, or override per-run with `--provider`/`--model`
- ChromaDB-backed vector store for code context retrieval
- Semantic chunking with function/class awareness
- Covers: general overview, architecture, security, per-file review, best practices, and improvement suggestions

### Quality score & rule engine
- Every review produces a deterministic **0-100 quality score** (with a letter grade) derived from static analysis findings — works even with `--no-ai`
- A configurable **rule engine** in `config.yaml` lets you define pass/fail policy (e.g. "score >= 70", "zero security issues") — `severity: fail` rules make CodeSentry exit non-zero, which is all you need to gate a CI pipeline or pre-commit hook

### Review guardrails
AI reviewers are noisy and can be manipulated, so every LLM call is wrapped in guardrails:
- **Triage gate**: files that are generated, trivial, or already clean are skipped. A clean file is one with no error/security/warning findings, where a quick LLM "LGTM?" check also agrees. The review budget goes to the riskiest files first.
- **Input guardrails**: secrets are redacted before code leaves your machine (and reported as findings). Comments or strings that try to instruct the AI reviewer ("ignore previous instructions", "approve this PR") are flagged, and that file can never be skipped.
- **Structured findings**: the LLM returns JSON findings with a line, severity, category, confidence, and a quoted `evidence` snippet, rather than free-form prose.
- **Output guardrails**: findings whose evidence doesn't exist in the code are dropped as hallucinations. Line-number drift is corrected, and low-confidence findings, nitpicks, no-op suggestions, duplicates and repeats of linter output are removed. Per-file and total caps keep the output short.
- **Critic**: a second, skeptical LLM pass sees only the code and the bare claim, not the reviewer's reasoning, and tries to refute each finding. Refuted findings are dropped.
- **Budget**: hard limits on LLM calls, files reviewed, and characters sent per file.

The HTML report and CLI output show which files were skipped and why, and how many findings each guardrail suppressed.

### GitHub PR review
- `codesentry-pr` reviews a pull request and posts **inline review comments** on the lines the PR changed, plus one summary comment that is updated in place on every push
- Ships as a **GitHub Action**, so any repository can add CodeSentry with a single workflow file
- Re-runs never repeat a comment: each one carries a fingerprint, and anything already posted is skipped
- Only lines *added* by the PR are commented on, and the quality score and rule engine are computed on those lines, so authors aren't blamed for pre-existing issues
- The PR title and description are never sent to the LLM; they are only scanned for prompt-injection attempts, which are flagged in the summary

### Reports
- HTML output with charts, score/grade, rule engine results, and an issue breakdown table
- Color-coded by severity
- Metrics from every layer in one place

## Prerequisites

- Python 3.8+
- An API key for whichever LLM provider you configure (or nothing at all, if you run a local Ollama server). The default provider is Hugging Face — [get a token here](https://huggingface.co/settings/tokens).

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

### 5. Set your LLM provider's API key

CodeSentry reads the key from the environment variable named in `config.yaml`'s active provider (`api_key_env`). For the default Hugging Face provider:

```bash
export HF_TOKEN="your_huggingface_token_here"
```

Or add it permanently to your shell profile:

```bash
echo 'export HF_TOKEN="your_huggingface_token_here"' >> ~/.bashrc
source ~/.bashrc
```

Using a different provider? Set `llm.provider` in `config.yaml` (or pass `--provider`) and export the matching key instead — e.g. `OPENAI_API_KEY` for OpenAI, `ANTHROPIC_API_KEY` for Claude, `GOOGLE_API_KEY` for Gemini. See [LLM providers](#llm-providers) below.

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

# Use a different LLM provider/model for this run only
codesentry --provider anthropic --model claude-sonnet-4-5

# Run in CI but never fail the build on rule violations (still reported)
codesentry --no-fail-on-rules
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
| `--provider` | | LLM provider to use, overriding `config.yaml` | from config |
| `--model` | | LLM model id to use, overriding `config.yaml` | from config |
| `--no-fail-on-rules` | | Always exit 0, even if a blocking rule fails | False |

### Exit codes

`codesentry` exits `1` if any `severity: fail` rule in the rule engine doesn't pass (see [Rule engine](#rule-engine)), so it can gate a CI job or pre-commit hook without extra scripting. Pass `--no-fail-on-rules` to always exit `0` while still printing/reporting rule results.

## Configuration

Edit `config.yaml` to adjust behavior. See the file itself for the full, commented reference — the sections below cover the parts worth knowing about.

### LLM providers

Set `llm.provider` to any key under `llm.providers`, and `llm.model` to that provider's model id:

```yaml
llm:
  provider: "huggingface"   # openai | anthropic | google | azure_openai | ollama | openrouter | groq | together | mistral | deepseek | custom | ...
  model: "Qwen/Qwen3.8-27B"
  max_tokens: 2000
  temperature: 0.3

  providers:
    huggingface:
      type: openai_compatible
      api_url: "https://router.huggingface.co/v1/chat/completions"
      api_key_env: "HF_TOKEN"
    openai:
      type: openai_compatible
      api_url: "https://api.openai.com/v1/chat/completions"
      api_key_env: "OPENAI_API_KEY"
    anthropic:
      type: anthropic
      api_url: "https://api.anthropic.com/v1/messages"
      api_key_env: "ANTHROPIC_API_KEY"
    ollama:
      type: openai_compatible
      api_url: "http://localhost:11434/v1/chat/completions"
      api_key_env: null   # no key needed for a local server
```

Every provider is called over plain HTTPS (no vendor SDKs), so adding another OpenAI-compatible endpoint (vLLM, LocalAI, LM Studio, a new hosted API, ...) is just a new entry with `type: openai_compatible`. `google` (Gemini) and `azure_openai` have their own `type` since their request/response shapes differ from the OpenAI format. Override the active provider/model per run with `--provider`/`--model` without touching the file.

### Static analysis languages

```yaml
static_analysis:
  file_extensions: [.py, .js, .jsx, .ts, .tsx, .java, .go, .rs, .rb, .php, .c, .h, .cpp, .cc, .hpp]
  languages:
    python:     { extensions: [.py], tools: [pylint, flake8, bandit, radon] }
    javascript: { extensions: [.js, .jsx, .ts, .tsx], tools: [eslint] }
    go:         { extensions: [.go], tools: [go_vet, gofmt, staticcheck] }
    rust:       { extensions: [.rs], tools: [clippy] }
    ruby:       { extensions: [.rb], tools: [rubocop] }
    php:        { extensions: [.php], tools: [php_lint] }
    java:       { extensions: [.java], tools: [checkstyle] }
    cpp:        { extensions: [.c, .h, .cpp, .cc, .hpp], tools: [cppcheck] }
```

A language's tools only run if you have the underlying binary installed (e.g. `npm i -g eslint`, `gem install rubocop`); missing tools are skipped with a message rather than failing the run.

### Quality scoring

```yaml
scoring:
  enabled: true
  base_score: 100
  weights:
    error: 5
    security: 8
    warning: 2
    info: 0.25
    high_complexity: 3
```

Every review computes a 0-100 score (with an A-F grade) from the weighted, per-file-averaged static analysis findings. It's deterministic and works even with `--no-ai`.

### Rule engine

```yaml
rules:
  enabled: true
  conditions:
    - name: "Minimum quality score"
      metric: score
      operator: ">="
      value: 70
      severity: fail   # non-zero exit code if this doesn't hold

    - name: "Limit high-complexity functions"
      metric: high_complexity_functions
      operator: "<="
      value: 5
      severity: warn   # reported, but never fails the run
```

Available metrics: `score`, `total_issues`, `error_issues`, `warning_issues`, `info_issues`, `security_issues`, `high_complexity_functions`. Available operators: `>=`, `<=`, `==`, `!=`, `>`, `<`. Use this to gate a CI job or pre-commit hook — `codesentry` exits `1` if any `severity: fail` rule fails (pass `--no-fail-on-rules` to always exit `0` while still reporting results).

### Guardrails

```yaml
guardrails:
  triage:
    mode: hybrid            # off | static | hybrid
    lgtm_confidence: 0.8    # how sure the LLM must be before a clean file is skipped
  input:
    redact_secrets: true
    detect_prompt_injection: true
  output:
    min_confidence: 0.6
    require_evidence: true  # every finding must quote real code
    suppress_nitpicks: true
    dedupe_against_static: true
    max_findings_per_file: 5
    max_findings_total: 25
  critic:
    enabled: true
    drop_uncertain: false   # true = keep only findings the critic upholds
  budget:
    max_llm_calls: 60
    max_files_to_review: 10
```

Triage modes:
- `off` reviews every file.
- `static` skips any file with no error/security/warning findings, without asking the LLM.
- `hybrid` (default) also requires a confident LLM "LGTM" before skipping.

Whatever the mode, these files are always reviewed:
- files with a detected secret or prompt-injection attempt
- files on security-sensitive paths (`*auth*`, `*crypto*`, `*payment*`, ...)
- files with static analysis issues

Suppressed findings are listed in the report by reason (`ungrounded_evidence`, `low_confidence`, `nitpick`, `duplicate_of_static_analysis`, `refuted_by_critic`, ...).

## GitHub integration

### As a GitHub Action (recommended)

In the repository you want reviewed, add `.github/workflows/codesentry.yml`:

```yaml
name: CodeSentry Review
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    if: github.event.pull_request.head.repo.full_name == github.repository
    steps:
      - uses: navyansh007/CodeSentry@main
        with:
          llm-provider: groq                 # any provider in config.yaml
          llm-model: openai/gpt-oss-120b
          llm-api-key: ${{ secrets.GROQ_API_KEY }}
```

Then add the provider's key as a repository secret. A copy of this workflow lives in [`examples/codesentry-pr-review.yml`](examples/codesentry-pr-review.yml).

| Input | Default | Description |
|---|---|---|
| `llm-provider` | `huggingface` | Provider key from `config.yaml` |
| `llm-model` | from config | Model id for that provider |
| `llm-api-key` | | Provider API key (pass from a secret) |
| `config` | `.codesentry.yaml` | Your repo's CodeSentry config; falls back to the bundled one |
| `no-ai` | `false` | Static analysis and guardrail checks only |
| `fail-on-rules` | `true` | Fail the job when a blocking rule fails |
| `github-token` | `github.token` | Token used to read the PR and post the review |

Outputs: `passed`, `findings`, `score`.

The action installs only lightweight dependencies (`requirements-pr.txt`), with no ChromaDB or PyTorch, so a run typically takes well under a minute plus LLM time. It never checks out or executes the PR's code: changed files are fetched through the API at the PR head commit and only analyzed statically.

**Forks:** GitHub doesn't expose secrets to `pull_request` runs from forks, which is why the example skips them. To review fork PRs you can use `pull_request_target`. Because CodeSentry never executes PR code this is reasonable, but read GitHub's guidance on `pull_request_target` before enabling it.

### From the command line

```bash
export GITHUB_TOKEN=...            # needs pull-requests: write, contents: read
export GROQ_API_KEY=...

codesentry-pr --repo owner/name --pr 42 --provider groq --model openai/gpt-oss-120b --dry-run
```

`--dry-run` prints the summary and every inline comment instead of posting them. Other options: `--no-ai`, `--no-fail-on-rules`, `--json-output result.json`, and `--api-url` for GitHub Enterprise Server. Inside GitHub Actions, `--repo` and `--pr` are detected automatically.

### PR review configuration

```yaml
github:
  max_files: 50
  skip_drafts: true
  include_static_findings: true          # post linter findings on added lines...
  static_severities: [error, security]   # ...of these severities only
  request_changes_on_critical: false     # "Request changes" instead of "Comment"
```

### What a PR review does

1. Fetches the changed files and their patches at the PR head commit.
2. Runs static analysis on them and keeps only the issues on added lines.
3. Runs triage. Generated files, comment-only changes and confidently clean changes are skipped. Diffs that remove a security control (`hmac.compare_digest`, `sanitize`, `login_required`, ...) or add a dangerous construct (`verify=False`, `shell=True`, `pickle.loads`, `innerHTML`, ...) are always reviewed.
4. Runs the AI review, with the PR's lines marked `+`. For large files, only the changed regions plus surrounding context are sent.
5. Applies the output guardrails, scoped to added lines, then the critic.
6. Posts one review with the new inline comments and updates the summary comment.

If GitHub rejects an inline position, findings are listed in the summary comment instead.

## Understanding the report

Reports land in the `reports/` directory as HTML files.

### Sections

1. **Analysis summary** — high-level stats with color-coded metrics
2. **Quality score** — the 0-100 score, letter grade, and languages analyzed
3. **Rule engine** — each configured rule's pass/fail/warn status
4. **AI analysis** — general codebase review and architectural notes
5. **Security analysis** — vulnerability assessments from the static layer and the AI layer
6. **Static analysis results** — issues from every language's linters, grouped by tool
7. **File-specific reviews** — per-file AI review (first 5 files by default)
8. **Best practices** — adherence to coding standards
9. **Improvement suggestions** — prioritized action items

### Severity levels

- **Error** — critical issues, fix immediately
- **Warning** — should be addressed
- **Info** — suggestions and notes
- **Security** — vulnerabilities flagged by a language's security tool (e.g. Bandit for Python)

## How it works

```
┌─────────────────────────────────────────────────────────┐
│                   CodeSentry CLI                        │
└────────────────┬────────────────────────────────────────┘
                 │
                 ├──► LAYER 1: Static Analysis (per language)
                 │    ├── Python  → Pylint, Flake8, Bandit, Radon
                 │    ├── JS/TS   → ESLint
                 │    ├── Go      → gofmt, go vet, staticcheck
                 │    ├── Rust    → cargo clippy
                 │    ├── Ruby    → RuboCop
                 │    ├── PHP     → php -l
                 │    ├── Java    → Checkstyle
                 │    └── C/C++   → cppcheck
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
                 │    └── Configurable LLM Provider
                 │        └── AI-powered review
                 │
                 ├──► Quality Scorer
                 │    └── 0-100 score + grade from static findings
                 │
                 ├──► Rule Engine
                 │    └── Pass/fail policy → CLI exit code
                 │
                 └──► Report Generator
                      └── HTML report with visualizations
```

### RAG

Code is chunked and embedded with sentence-transformers, stored in ChromaDB. When reviewing, the most relevant chunks are retrieved and stuffed into the LLM prompt. That way the model actually sees related code from elsewhere in the repo, not just whatever's in the immediate file.

## Research behind the guardrails

The guardrails follow recent work on why automated code review is noisy and how it gets attacked:

| Paper | What it found | What CodeSentry does with it |
|---|---|---|
| [SWR-Bench](https://arxiv.org/abs/2509.01494) (2025) | LLM review tools averaged ~9% precision on real PRs | Precision-first design: structured findings plus a deterministic filter chain |
| [Is Agentic Code Review Helpful?](https://arxiv.org/abs/2607.03316) (Jul 2026) | 56% of CodeRabbit's comments were rejected by developers | Triage gate, nitpick suppression, confidence floor, and per-file caps |
| [HalluJudge](https://arxiv.org/abs/2601.19072) (Jan 2026) | Review comments are often not grounded in the code they discuss | Every finding must quote evidence that is located in the file, or it is dropped |
| [OpenCodeReview](https://arxiv.org/abs/2608.09290) (Aug 2026) | A reflection step that only *filters*, and sees only the code rather than the agent's reasoning, keeps precision high at volume | The critic sees the bare claim plus code, can only drop findings, and fails open |
| [Adversarial Review](https://arxiv.org/abs/2608.18167) (Aug 2026) | A critic that is asked to disagree yields better-grounded reviews | The critic is prompted to *refute* each claim, not to agree with it |
| [SEVRA-BENCH](https://arxiv.org/abs/2606.13757) (Jun 2026) | Review agents can be socially engineered into approving PRs that revert CVE fixes | Code and PR text are treated as untrusted. PR descriptions are never sent to the LLM. Diff-only security-regression checks force a review |
| [The End of Code Review](https://arxiv.org/abs/2606.13175) (Jun 2026) | Instructions embedded in code can steer a reviewing agent | Prompt-injection detection, plus fencing of untrusted content in every prompt |

## Supported languages

Both static analysis and the AI layer cover:
- Python (.py)
- JavaScript (.js, .jsx) / TypeScript (.ts, .tsx)
- Java (.java)
- C/C++ (.c, .h, .cpp, .cc, .hpp)
- Go (.go)
- Rust (.rs)
- Ruby (.rb)
- PHP (.php)

## Contributing

PRs welcome. A plugin system for custom analyzers would be a good next step, as would native SDK support for providers with richer feature sets (tool calling, prompt caching) than the plain-HTTP interface here uses. CI/CD integration improvements are also useful — the current example is pretty bare.

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

For inline comments on GitHub pull requests, use the [GitHub Action](#github-integration) instead.

## Running the tests

```bash
python -m unittest discover -s tests -v
```

The suite uses fake LLM and GitHub clients, so it needs no API keys or network access.

## Troubleshooting

**`HTTP 402` / `410` from Hugging Face**: `402` means the account has no Inference Providers credits left; `410` means the provider retired the model. Switch `llm.model`, or use another provider with `--provider`.

**`codesentry-pr` fails with 401/403**: the token needs `pull-requests: write` and `contents: read`. In Actions, add the `permissions:` block from the example workflow.

**"`<VAR>` environment variable not set"** — export the API key for your active provider before running (see `api_key_env` for that provider in `config.yaml`):
```bash
export HF_TOKEN="your_token_here"   # or OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
```

**ChromaDB permission errors** — check write permissions in the directory where `.chroma_db` is created.

**Timeouts on large codebases** — use `--no-ai` for a faster run, or increase `llm.timeout` in `config.yaml`.

**No supported files found** — check `static_analysis.file_extensions` in `config.yaml` covers your project's languages, or use `--no-static` to skip static analysis entirely.

**A language's linter isn't running** — its tool isn't installed on PATH. CodeSentry skips missing tools with a message rather than failing; install the one you need (see [Static analysis languages](#static-analysis-languages) above).

## License

Provided as-is for educational and professional use.

## Acknowledgments

- [Qwen](https://huggingface.co/Qwen) by Alibaba Cloud (the default model, via Hugging Face)
- [ChromaDB](https://www.trychroma.com/)
- [Sentence Transformers](https://www.sbert.net/)
- Pylint, Flake8, Bandit, Radon, ESLint, gofmt/go vet/staticcheck, Clippy, RuboCop, Checkstyle, cppcheck
