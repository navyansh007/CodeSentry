"""
AI Review Layer - LLM-powered code review against any configured provider
"""

import os
from typing import TYPE_CHECKING, List, Dict, Any, Optional
from .llm_providers import create_provider, LLMProviderError
from .findings import Finding, parse_findings, FINDINGS_SCHEMA_PROMPT
from .guardrails import (
    InputGuardrails, OutputGuardrails, UNTRUSTED_PREAMBLE, fence_untrusted, redact_secrets,
)
from .triage import ReviewTriage
from .critic import FindingCritic
from .diff_utils import numbered_windows

if TYPE_CHECKING:  # chromadb/torch are only needed for full-repo RAG review, not PR review
    from .rag_system import RAGSystem


class AIReviewer:
    """AI-powered code reviewer using a configurable LLM provider with RAG"""

    SYSTEM_PROMPT = (
        "You are an expert code reviewer with deep knowledge of software "
        "engineering best practices, security, and performance optimization."
    )

    def __init__(self, config: Dict[str, Any], rag_system: Optional['RAGSystem']):
        self.config = config
        self.rag_system = rag_system

        try:
            self.provider = create_provider(config)
        except LLMProviderError as e:
            print(f"Warning: {str(e)}")
            self.provider = None

        if self.provider and not self.provider.is_configured():
            print(f"Warning: {self.provider.missing_key_message()}")

        budget_cfg = (config.get('guardrails', {}) or {}).get('budget', {}) or {}
        self.max_llm_calls = int(budget_cfg.get('max_llm_calls', 60))
        self.max_files_to_review = int(budget_cfg.get('max_files_to_review', 10))
        self.max_file_chars = int(budget_cfg.get('max_file_chars', 12000))
        self.llm_calls = 0

        self.input_guardrails = InputGuardrails(config)
        self.output_guardrails = OutputGuardrails(config)
        self.triage = ReviewTriage(config)
        self.critic = FindingCritic(config, self._call_llm)

        self.review_results = {
            'general_review': '',
            'file_reviews': [],
            'architectural_insights': '',
            'security_concerns': [],
            'best_practices': [],
            'improvement_suggestions': [],
            'findings': [],
            'triage': [],
            'guardrail_stats': {},
        }

    def perform_review(self, files: List[str], static_results: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive AI-powered code review"""
        print("\nPerforming AI-powered code review...")

        # 1. General codebase overview
        print("  Generating general codebase review...")
        self.review_results['general_review'] = self._review_general_codebase()

        # 2. Architectural analysis
        print("  Analyzing architecture...")
        self.review_results['architectural_insights'] = self._analyze_architecture(files)

        # 3. Security analysis
        print("  Analyzing security concerns...")
        self.review_results['security_concerns'] = self._analyze_security(static_results)

        # 4. File-specific reviews (triaged, guarded, and verified)
        print("  Reviewing individual files...")
        self.review_results['file_reviews'] = self._review_files(files, static_results)

        # 5. Best practices check
        print("  Checking best practices...")
        self.review_results['best_practices'] = self._check_best_practices()

        # 6. Generate improvement suggestions
        print("  Generating improvement suggestions...")
        self.review_results['improvement_suggestions'] = self._generate_suggestions(static_results)

        return self.review_results

    def _review_general_codebase(self) -> str:
        """Generate general codebase review"""
        # Get diverse code samples
        samples = self.rag_system.get_diverse_samples(n_samples=8)

        if not samples:
            return "Unable to generate review: no code samples available"

        # Build context
        context = self._build_context_from_samples(samples)

        # Create prompt
        prompt = f"""You are an expert code reviewer. Analyze the following codebase samples and provide a comprehensive overview.

Context from codebase:
{context}

Please provide:
1. Overall code quality assessment
2. Code organization and structure
3. Notable patterns or anti-patterns
4. General observations

Keep your response concise and actionable."""

        return self._call_llm(prompt)

    def _analyze_architecture(self, files: List[str]) -> str:
        """Analyze codebase architecture"""
        # Get structural information
        file_structure = self._analyze_file_structure(files)

        prompt = f"""Analyze the architecture of this codebase based on the following file structure:

{file_structure}

Provide insights on:
1. Project organization and modularity
2. Separation of concerns
3. Potential architectural improvements
4. Scalability considerations

Be specific and actionable."""

        return self._call_llm(prompt)

    def _analyze_security(self, static_results: Dict[str, Any]) -> List[str]:
        """Analyze security concerns"""
        concerns = []

        # Get security issues from static analysis
        bandit_issues = static_results.get('bandit', [])

        if bandit_issues:
            # Get relevant code context for security issues
            for issue in bandit_issues[:5]:  # Analyze top 5 security issues
                file_path = issue.get('filename', '')
                line_num = issue.get('line_number', 0)
                issue_text = issue.get('issue_text', '')

                # Retrieve context from RAG
                context_chunks = self.rag_system.retrieve_file_context(file_path)

                if context_chunks:
                    context = redact_secrets(context_chunks[0]['content']).text

                    prompt = f"""Analyze this security issue:

Issue: {issue_text}
File: {file_path}
Line: {line_num}

Code context:
{context[:500]}

Provide:
1. Severity assessment
2. Potential impact
3. Recommended fix
4. Prevention strategy

Be concise."""

                    analysis = self._call_llm(prompt)
                    concerns.append({
                        'issue': issue_text,
                        'file': file_path,
                        'line': line_num,
                        'analysis': analysis
                    })

        return concerns

    FILE_REVIEW_PROMPT = """Review the following code file as a senior engineer.

{preamble}

File: {file}
Language: {language}
{static_hint}{diff_hint}
{code}

Focus on real defects: bugs, logic errors, unhandled edge cases, security problems,
performance problems, and error handling. Mention design or readability only when a
materially better approach exists. Do not restate issues a linter already reported.
Line numbers are shown at the left of each line.

{schema}"""

    def _review_files(self, files: List[str], static_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Triage every file, then review the riskiest ones with the guardrail pipeline"""
        static_issues = static_results.get('issues', []) or []
        complexity = self._complexity_by_file(static_results)

        contents: Dict[str, str] = {}
        sanitized_by_file = {}
        decisions = []
        for file_path in files:
            content = self._read_file(file_path)
            if content is None:
                continue
            contents[file_path] = content
            sanitized = self.input_guardrails.sanitize(content)
            sanitized_by_file[file_path] = sanitized
            file_issues = [i for i in static_issues if i.get('file') == file_path]
            decision = self.triage.decide(
                file_path, content, file_issues, sanitized,
                high_complexity=complexity.get(file_path, 0),
                llm_call=self._call_llm if self._llm_available() else None,
            )
            decisions.append(decision)

        to_review = sorted((d for d in decisions if not d.skipped), key=lambda d: d.risk, reverse=True)
        for decision in to_review[self.max_files_to_review:]:
            decision.action = 'skip'
            decision.reason = f'review budget reached (max_files_to_review={self.max_files_to_review})'
        to_review = to_review[:self.max_files_to_review]

        skipped = sum(1 for d in decisions if d.skipped)
        print(f"    Triage: {len(to_review)} file(s) to review, {skipped} skipped")

        all_findings: List[Finding] = []
        reviewed_files = []
        for decision in to_review:
            file_path = decision.file
            sanitized = sanitized_by_file[file_path]
            findings = self.input_guardrails.findings_for(file_path, sanitized)
            verdict = 'NEEDS_CHANGES' if findings else 'LGTM'
            ai_findings = self._review_single_file(file_path, sanitized.text, static_issues)
            if ai_findings is None:
                verdict = 'ERROR'
            else:
                findings.extend(ai_findings)
            all_findings.extend(findings)
            reviewed_files.append((file_path, verdict))

        file_lines = {path: text.splitlines() for path, text in contents.items()}
        report = self.output_guardrails.apply(all_findings, file_lines, static_issues)
        kept, critic_dropped = self.critic.verify(
            report.kept, file_lines, redact=lambda text: redact_secrets(text).text,
        )
        report.kept = sorted(kept, key=lambda f: (f.file, f.line))
        report.dropped.extend(critic_dropped)

        self.review_results['findings'] = [f.to_dict() for f in report.kept]
        self.review_results['triage'] = [
            {'file': d.file, 'action': d.action, 'reason': d.reason, 'risk': d.risk} for d in decisions
        ]
        self.review_results['guardrail_stats'] = {
            'files_total': len(decisions),
            'files_reviewed': len(to_review),
            'files_skipped': len(decisions) - len(to_review),
            'findings_raw': len(all_findings),
            'findings_kept': len(report.kept),
            'dropped_by_reason': report.drop_counts(),
            'llm_calls': self.llm_calls,
        }
        print(f"    Guardrails kept {len(report.kept)} of {len(all_findings)} finding(s)")

        reviews = []
        for file_path, verdict in reviewed_files:
            file_findings = [f for f in report.kept if f.file == file_path]
            if verdict == 'ERROR' and not file_findings:
                body = 'AI review could not be completed for this file.'
            elif not file_findings:
                body = '✅ No issues found. The code looks correct and there is no materially better approach.'
            else:
                body = '\n\n---\n\n'.join(f"**Line {f.line}** · {f.to_markdown()}" for f in file_findings)
            reviews.append({
                'file': file_path,
                'review': body,
                'findings': [f.to_dict() for f in file_findings],
                'verdict': 'NEEDS_CHANGES' if file_findings else ('ERROR' if verdict == 'ERROR' else 'LGTM'),
            })
        return reviews

    def _review_single_file(self, file_path: str, content: str,
                            static_issues: List[Dict[str, Any]],
                            changed_lines: Optional[set] = None,
                            extra_hints: Optional[List[str]] = None) -> Optional[List[Finding]]:
        """
        Ask the LLM for structured findings on one (already sanitized) file.

        `changed_lines` (PR mode) marks the lines the pull request added with
        a `+` so the model focuses on new code; `extra_hints` are appended to
        the prompt (e.g. security-regression signals found in the diff).
        """
        lines = content.splitlines()
        if changed_lines is not None:
            numbered = '\n'.join(
                f"{'+' if n in changed_lines else ' '}{n:>5} | {line}" for n, line in enumerate(lines, 1)
            )
            if len(numbered) > self.max_file_chars:
                # Large file: show the changed regions with context instead of the head
                numbered = numbered_windows(lines, changed_lines, context=25)
        else:
            numbered = '\n'.join(f'{n:>5} | {line}' for n, line in enumerate(lines, 1))
        if len(numbered) > self.max_file_chars:
            numbered = numbered[:self.max_file_chars] + '\n   ... (truncated)'

        file_issues = [i for i in static_issues if i.get('file') == file_path]
        static_hint = ''
        if file_issues:
            listed = '\n'.join(
                f"- line {i.get('line')}: [{i.get('tool')}] {i.get('message', '')[:120]}" for i in file_issues[:15]
            )
            static_hint = f"Already reported by static analysis (do not repeat):\n{listed}\n"

        diff_hint = ''
        if changed_lines is not None:
            diff_hint = ("This file is part of a pull request. Lines marked with '+' were added or "
                         "changed by the PR. Only report problems on those lines, though you may use "
                         "the rest of the file as context.\n")
        for hint in extra_hints or []:
            diff_hint += f"{hint}\n"

        prompt = self.FILE_REVIEW_PROMPT.format(
            preamble=UNTRUSTED_PREAMBLE,
            file=file_path,
            language=self._language_of(file_path),
            static_hint=static_hint,
            diff_hint=diff_hint,
            code=fence_untrusted(numbered, os.path.basename(file_path)),
            schema=FINDINGS_SCHEMA_PROMPT,
        )
        response = self._call_llm(prompt)
        if self._is_error(response):
            return None
        findings = parse_findings(response, file_path)
        if findings is None:
            # One repair attempt: models occasionally wrap JSON in prose
            retry = self._call_llm(
                "Your previous answer was not valid JSON. Return ONLY the JSON object described.\n\n"
                + FINDINGS_SCHEMA_PROMPT + "\n\nPrevious answer:\n" + response[:3000]
            )
            findings = None if self._is_error(retry) else parse_findings(retry, file_path)
        if findings is None:
            return None
        for finding in findings:
            finding.file = file_path  # never trust a model-supplied path
        return findings

    @staticmethod
    def _complexity_by_file(static_results: Dict[str, Any]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for file_data in static_results.get('radon', []) or []:
            for path, functions in (file_data.get('complexity') or {}).items():
                if isinstance(functions, list):
                    high = sum(1 for fn in functions if isinstance(fn, dict) and fn.get('complexity', 0) > 10)
                    counts[file_data.get('file', path)] = counts.get(file_data.get('file', path), 0) + high
        return counts

    @staticmethod
    def _read_file(file_path: str) -> Optional[str]:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except OSError:
            return None

    @staticmethod
    def _language_of(file_path: str) -> str:
        from .utils import get_file_language
        return get_file_language(file_path)

    @staticmethod
    def _is_error(response: Any) -> bool:
        return not isinstance(response, str) or response.startswith('Error:')

    def _llm_available(self) -> bool:
        return bool(self.provider and self.provider.is_configured())

    def _check_best_practices(self) -> List[str]:
        """Check for best practices"""
        samples = self.rag_system.get_diverse_samples(n_samples=5)

        if not samples:
            return []

        context = self._build_context_from_samples(samples)

        prompt = f"""Analyze these code samples for adherence to best practices:

{context}

Identify:
1. Violations of coding best practices
2. Missing documentation or comments
3. Naming convention issues
4. Code duplication
5. Error handling gaps

Provide specific examples with line references when possible."""

        response = self._call_llm(prompt)

        # Split response into list items
        practices = [item.strip() for item in response.split('\n') if item.strip()]
        return practices

    def _generate_suggestions(self, static_results: Dict[str, Any]) -> List[str]:
        """Generate improvement suggestions based on static analysis"""
        suggestions = []

        summary = static_results.get('summary', {})

        prompt = f"""Based on static analysis results, provide improvement suggestions:

Static Analysis Summary:
- Total Issues: {summary.get('total_issues', 0)}
- Pylint Issues: {summary.get('pylint_issues', 0)}
- Flake8 Issues: {summary.get('flake8_issues', 0)}
- Security Issues: {summary.get('bandit_issues', 0)}
- High Complexity Functions: {summary.get('high_complexity_functions', 0)}

Severity Breakdown:
- Errors: {summary.get('severity_breakdown', {}).get('error', 0)}
- Warnings: {summary.get('severity_breakdown', {}).get('warning', 0)}
- Security: {summary.get('severity_breakdown', {}).get('security', 0)}

Provide 5-7 prioritized improvement suggestions for this codebase."""

        response = self._call_llm(prompt)

        # Split into list
        suggestions = [item.strip() for item in response.split('\n') if item.strip() and len(item.strip()) > 10]
        return suggestions[:7]

    def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM provider"""
        if not self.provider:
            return "Error: no LLM provider configured"
        if not self.provider.is_configured():
            return f"Error: {self.provider.missing_key_message()}"
        if self.llm_calls >= self.max_llm_calls:
            return f"Error: LLM call budget exhausted (max_llm_calls={self.max_llm_calls})"

        self.llm_calls += 1
        try:
            return self.provider.chat(prompt, self.SYSTEM_PROMPT)
        except Exception as e:
            return f"Error: {str(e)}"

    def _build_context_from_samples(self, samples: List[Dict[str, Any]]) -> str:
        """Build context string from code samples"""
        context_parts = []

        for sample in samples:
            metadata = sample['metadata']
            content = redact_secrets(sample['content']).text

            context_parts.append(f"""
File: {metadata['file_path']}
Lines: {metadata['start_line']}-{metadata['end_line']}

```
{content[:800]}
```
""")

        return '\n'.join(context_parts)

    def _analyze_file_structure(self, files: List[str]) -> str:
        """Analyze and format file structure"""
        # Group files by directory
        structure = {}

        for file_path in files:
            parts = file_path.split(os.sep)
            if len(parts) > 1:
                directory = os.sep.join(parts[:-1])
                filename = parts[-1]

                if directory not in structure:
                    structure[directory] = []
                structure[directory].append(filename)

        # Format structure
        formatted = []
        for directory, filenames in sorted(structure.items()):
            formatted.append(f"\n{directory}/")
            for filename in sorted(filenames):
                formatted.append(f"  - {filename}")

        return '\n'.join(formatted)
