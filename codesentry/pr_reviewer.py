"""
PR Reviewer - Review a GitHub pull request and post inline comments

Pipeline for one pull request:
  1. Fetch the PR, its changed files and patches, and each file's content
     at the PR head commit (so line numbers match the diff exactly).
  2. Run static analysis on the changed files and keep only issues that land
     on lines the PR added - pre-existing problems are not the author's fault.
  3. Triage: skip files that are generated, trivial, comment-only changes,
     or confidently clean. Security-regression signals force a review.
  4. AI review of the remaining files, marking the PR's lines with `+`.
  5. Output guardrails scoped to added lines, then the falsification critic.
  6. Post one review with inline comments, skipping anything already posted
     on a previous run (fingerprint markers), and upsert a summary comment.

The PR title/description are never sent to the LLM. SEVRA-BENCH
(arXiv:2606.13757) shows that persuasive PR narratives are how review agents
get socially engineered into approving vulnerable changes; CodeSentry only
scans that text for prompt-injection attempts and reports them.
"""

import os
import re
import shutil
import tempfile
from typing import Any, Dict, List, Optional

from .ai_reviewer import AIReviewer
from .critic import FindingCritic
from .diff_utils import PatchInfo, parse_patch
from .findings import Finding
from .github_client import GitHubClient, GitHubError
from .guardrails import (
    InputGuardrails, OutputGuardrails, detect_prompt_injection,
    detect_security_regressions, redact_secrets,
)
from .rule_engine import RuleEngine, RuleEngineError
from .scoring import QualityScorer
from .static_analyzer import StaticAnalyzer
from .triage import ReviewTriage
from .utils import should_exclude

SUMMARY_MARKER = '<!-- codesentry:summary -->'
FINGERPRINT_MARKER = '<!-- codesentry:fp={fp} -->'
_FINGERPRINT_RE = re.compile(r'<!-- codesentry:fp=([0-9a-f]{6,40}) -->')

_STATIC_SEVERITY_MAP = {'security': 'critical', 'error': 'major', 'warning': 'minor', 'info': 'nit'}
_SIGNAL_TITLES = {
    'security_control_removed': 'Security check removed without a replacement',
    'tls_verification_disabled': 'TLS certificate verification disabled',
    'shell_injection_risk': 'Command executed through a shell',
    'dynamic_code_execution': 'Dynamic code execution',
    'unsafe_deserialization': 'Unsafe deserialization',
    'xss_sink': 'Unescaped HTML output (XSS sink)',
    'security_check_suppressed': 'Security check suppressed',
    'weak_crypto': 'Weak cryptographic primitive',
    'debug_enabled': 'Debug mode enabled',
}


class PRReviewer:
    """Reviews one pull request end-to-end"""

    def __init__(self, config: Dict[str, Any], client: GitHubClient, use_ai: bool = True):
        self.config = config
        self.client = client
        self.use_ai = use_ai
        gh_cfg = config.get('github', {}) or {}
        self.max_files = int(gh_cfg.get('max_files', 50))
        self.skip_drafts = gh_cfg.get('skip_drafts', True)
        self.include_static = gh_cfg.get('include_static_findings', True)
        self.static_severities = set(gh_cfg.get('static_severities', ['error', 'security']))
        self.request_changes_on_critical = gh_cfg.get('request_changes_on_critical', False)
        self.extensions = tuple(config.get('static_analysis', {}).get('file_extensions', []))

        self.input_guardrails = InputGuardrails(config)
        self.output_guardrails = OutputGuardrails(config)
        self.triage = ReviewTriage(config)
        self.reviewer = AIReviewer(config, rag_system=None) if use_ai else None
        llm_call = self.reviewer._call_llm if self.reviewer else (lambda prompt: 'Error: AI disabled')
        self.critic = FindingCritic(config, llm_call)

    # ------------------------------------------------------------------

    def run(self, number: int, dry_run: bool = False) -> Dict[str, Any]:
        pr = self.client.get_pull(number)
        head_sha = pr['head']['sha']

        if self.skip_drafts and pr.get('draft'):
            return {'status': 'skipped', 'reason': 'draft pull request', 'passed': True}

        pr_text_injections = detect_prompt_injection(f"{pr.get('title') or ''}\n{pr.get('body') or ''}")

        changed = self._select_files(self.client.list_pull_files(number))
        workdir = tempfile.mkdtemp(prefix='codesentry-pr-')
        try:
            files = self._materialize(changed, head_sha, workdir)
            result = self._review(files, workdir)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        result['pr_text_injections'] = pr_text_injections
        result['head_sha'] = head_sha
        posted = self._existing_fingerprints(number)
        new_findings = [f for f in result['findings'] if f.fingerprint not in posted]
        result['already_posted'] = len(result['findings']) - len(new_findings)
        comments = [self._to_comment(f, files[f.file]['patch']) for f in new_findings]
        result['comments'] = comments
        result['summary'] = self._summary(result, number)
        result['event'] = self._event(result)

        if dry_run:
            result['status'] = 'dry_run'
            return result

        self._post(number, head_sha, result)
        result['status'] = 'posted'
        return result

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    def _select_files(self, pr_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        selected = []
        for f in pr_files:
            name = f.get('filename', '')
            if f.get('status') == 'removed' or not f.get('patch'):
                continue  # deleted, binary, or too large for GitHub to diff
            if self.extensions and not name.endswith(self.extensions):
                continue
            if should_exclude(name, self.config):
                continue
            selected.append(f)
        return selected[:self.max_files]

    def _materialize(self, changed: List[Dict[str, Any]], head_sha: str, workdir: str) -> Dict[str, Dict[str, Any]]:
        """Write each changed file (at the head commit) into `workdir`"""
        files: Dict[str, Dict[str, Any]] = {}
        for f in changed:
            rel = f['filename']
            content = self.client.get_file_content(rel, head_sha)
            if content is None:
                continue
            abs_path = os.path.join(workdir, rel)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, 'w', encoding='utf-8') as fh:
                fh.write(content)
            files[rel] = {'abs': abs_path, 'content': content, 'patch': parse_patch(f['patch'])}
        return files

    def _existing_fingerprints(self, number: int) -> set:
        try:
            comments = self.client.list_review_comments(number)
        except GitHubError:
            return set()
        return {m.group(1) for c in comments for m in _FINGERPRINT_RE.finditer(c.get('body') or '')}

    # ------------------------------------------------------------------
    # Review
    # ------------------------------------------------------------------

    def _review(self, files: Dict[str, Dict[str, Any]], workdir: str) -> Dict[str, Any]:
        static_results = self._static(files, workdir)
        static_issues = static_results.get('issues', [])

        findings: List[Finding] = []
        decisions = []
        file_lines = {rel: data['content'].splitlines() for rel, data in files.items()}
        added = {rel: data['patch'].added_lines for rel, data in files.items()}
        llm_available = self.reviewer is not None and self.reviewer._llm_available()

        for rel, data in files.items():
            patch: PatchInfo = data['patch']
            sanitized = self.input_guardrails.sanitize(data['content'])
            file_issues = [i for i in static_issues if i.get('file') == rel]
            new_issues = [i for i in file_issues if int(i.get('line') or 0) in patch.added_lines]
            signals = detect_security_regressions(patch.removed_content, patch.changed_text)

            decision = self.triage.decide(
                rel, data['content'], new_issues, sanitized,
                changed_lines=patch.changed_text,
                llm_call=self.reviewer._call_llm if llm_available else None,
                must_review_reasons=[f"security signal: {s['type']}" for s in signals] or None,
                focus_lines=patch.added_lines,
            )
            decisions.append(decision)

            findings.extend(self.input_guardrails.findings_for(rel, sanitized))
            findings.extend(self._signal_findings(rel, signals, patch))
            if self.include_static:
                findings.extend(self._static_findings(rel, new_issues))

            if decision.skipped or not llm_available:
                continue
            hints = [f"Diff signal ({s['type']}): `{s['snippet']}`" for s in signals]
            ai_findings = self.reviewer._review_single_file(
                rel, sanitized.text, static_issues, changed_lines=patch.added_lines, extra_hints=hints,
            )
            findings.extend(ai_findings or [])

        report = self.output_guardrails.apply(findings, file_lines, static_issues, allowed_lines=added)
        kept, critic_dropped = self.critic.verify(
            report.kept, file_lines, redact=lambda text: redact_secrets(text).text,
        ) if llm_available else (report.kept, [])
        report.dropped.extend(critic_dropped)

        scorer = QualityScorer(self.config)
        new_static = {'summary': self._summarize([i for i in static_issues
                                                  if int(i.get('line') or 0) in added.get(i.get('file'), set())])}
        score = scorer.calculate(new_static, max(len(files), 1))
        rules = {'passed': True, 'results': [], 'enabled': False}
        try:
            engine = RuleEngine(self.config)
            rules = engine.evaluate(RuleEngine.build_metrics(score, new_static['summary']))
        except RuleEngineError as e:
            rules['error'] = str(e)

        return {
            'findings': sorted(kept, key=lambda f: (f.file, f.line)),
            'files': files,
            'triage': decisions,
            'dropped_by_reason': report.drop_counts(),
            'findings_raw': len(findings),
            'score': score,
            'rules': rules,
            'passed': rules.get('passed', True),
            'llm_calls': self.reviewer.llm_calls if self.reviewer else 0,
        }

    def _static(self, files: Dict[str, Dict[str, Any]], workdir: str) -> Dict[str, Any]:
        if not files:
            return {'issues': []}
        analyzer = StaticAnalyzer(self.config)
        results = analyzer.analyze([d['abs'] for d in files.values()], project_path=workdir)
        prefix = workdir.rstrip(os.sep) + os.sep
        real_prefix = os.path.realpath(workdir).rstrip(os.sep) + os.sep
        for issue in results.get('issues', []):
            path = issue.get('file') or ''
            for p in (prefix, real_prefix):
                if path.startswith(p):
                    path = path[len(p):]
                    break
            issue['file'] = path.replace(os.sep, '/')
        return results

    @staticmethod
    def _summarize(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        breakdown = {'error': 0, 'warning': 0, 'info': 0, 'security': 0}
        for issue in issues:
            breakdown[issue.get('severity', 'info')] = breakdown.get(issue.get('severity', 'info'), 0) + 1
        return {'total_issues': len(issues), 'severity_breakdown': breakdown, 'high_complexity_functions': 0}

    def _static_findings(self, rel: str, issues: List[Dict[str, Any]]) -> List[Finding]:
        out = []
        for issue in issues:
            if issue.get('severity') not in self.static_severities:
                continue
            code = f" ({issue['code']})" if issue.get('code') else ''
            out.append(Finding(
                file=rel, line=int(issue.get('line') or 0),
                title=f"{issue.get('message', '').strip()[:150]}{code}",
                body=f"Reported by `{issue.get('tool')}`.",
                severity=_STATIC_SEVERITY_MAP.get(issue.get('severity'), 'minor'),
                category='security' if issue.get('severity') == 'security' else 'bug',
                confidence=1.0, source=f"static:{issue.get('tool')}",
            ))
        return out

    @staticmethod
    def _signal_findings(rel: str, signals: List[Dict[str, Any]], patch: PatchInfo) -> List[Finding]:
        """Dangerous additions become findings (verified by the critic like AI ones)"""
        added_sorted = sorted(patch.added_content)
        out = []
        for signal in signals:
            if 'index' not in signal:
                continue  # removals have no new-side line to comment on; used as review hints
            line = added_sorted[signal['index']]
            out.append(Finding(
                file=rel, line=line,
                title=_SIGNAL_TITLES.get(signal['type'], signal['type'].replace('_', ' ')),
                body='This change introduces a construct that is a common source of vulnerabilities. '
                     'Confirm it is necessary and safe here.',
                severity='major', category='security', confidence=0.7,
                evidence=patch.added_content[line], source='heuristic:security',
            ))
        return out

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    @staticmethod
    def _to_comment(finding: Finding, patch: PatchInfo) -> Dict[str, Any]:
        body = finding.to_markdown()
        if finding.verdict == 'UPHELD' and finding.verdict_reason:
            body += f"\n\n<sub>Verified by CodeSentry critic: {finding.verdict_reason}</sub>"
        body += '\n\n' + FINGERPRINT_MARKER.format(fp=finding.fingerprint)
        comment: Dict[str, Any] = {'path': finding.file, 'line': finding.line, 'side': 'RIGHT', 'body': body}
        end = finding.end_line
        if end and end > finding.line and all(n in patch.commentable_lines for n in range(finding.line, end + 1)):
            comment['start_line'] = finding.line
            comment['line'] = end
            comment['start_side'] = 'RIGHT'
        return comment

    def _event(self, result: Dict[str, Any]) -> str:
        if self.request_changes_on_critical and (
            any(f.severity == 'critical' for f in result['findings']) or not result['passed']
        ):
            return 'REQUEST_CHANGES'
        return 'COMMENT'

    def _summary(self, result: Dict[str, Any], number: int) -> str:
        score = result['score']
        reviewed = [d for d in result['triage'] if not d.skipped]
        skipped = [d for d in result['triage'] if d.skipped]
        counts: Dict[str, int] = {}
        for f in result['findings']:
            counts[f.severity] = counts.get(f.severity, 0) + 1

        lines = [SUMMARY_MARKER, '## 🛡️ CodeSentry Review', '']
        status = '✅ No blocking issues found' if result['passed'] and not counts.get('critical') \
            else '❌ Blocking issues found'
        lines.append(f"**{status}** · Quality score on changed lines: **{score['score']}/100 ({score['grade']})**")
        lines.append('')
        if result['findings']:
            parts = [f"{counts[s]} {s}" for s in ('critical', 'major', 'minor', 'nit') if counts.get(s)]
            lines.append(f"**{len(result['findings'])} finding(s):** {', '.join(parts)}"
                         + (f" ({result['already_posted']} already posted earlier)" if result['already_posted'] else ''))
        else:
            lines.append('No issues found in the changed code.')
        lines.append('')

        if result['pr_text_injections']:
            lines.append('> [!WARNING]')
            lines.append('> The PR title or description contains text that appears to instruct AI reviewers '
                         f"(e.g. `{result['pr_text_injections'][0]['snippet'][:80]}`). CodeSentry never "
                         'sends PR descriptions to the LLM, but human reviewers should take note.')
            lines.append('')

        if result['rules'].get('enabled') and result['rules'].get('results'):
            lines.append('<details><summary>Rule engine</summary>\n')
            lines.append('| Rule | Result |')
            lines.append('|---|---|')
            for rule in result['rules']['results']:
                icon = '✅' if rule['passed'] else ('⚠️' if rule['severity'] == 'warn' else '❌')
                lines.append(f"| {rule['name']} | {icon} {rule['metric']} {rule['operator']} "
                             f"{rule['expected']} (actual: {rule['actual']}) |")
            lines.append('\n</details>\n')

        lines.append('<details><summary>Guardrails</summary>\n')
        lines.append(f"- Files reviewed by AI: {len(reviewed)} · skipped by triage: {len(skipped)}")
        lines.append(f"- Findings kept: {len(result['findings'])} of {result['findings_raw']} · "
                     f"LLM calls: {result['llm_calls']}")
        for reason, count in sorted(result['dropped_by_reason'].items()):
            lines.append(f"- Suppressed {count} as _{reason.replace('_', ' ')}_")
        if skipped:
            lines.append('')
            lines.append('Skipped files:')
            for d in skipped[:25]:
                lines.append(f"- `{d.file}`: {d.reason}")
        lines.append('\n</details>\n')
        lines.append(f"<sub>Reviewed commit {result['head_sha'][:7]} · "
                     "comments only cover lines added in this PR</sub>")
        return '\n'.join(lines)

    def _post(self, number: int, head_sha: str, result: Dict[str, Any]) -> None:
        comments = result['comments']
        if comments or result['event'] != 'COMMENT':
            body = f"CodeSentry found {len(comments)} new issue(s). See the summary comment for details."
            try:
                self.client.create_review(number, head_sha, body, comments, event=result['event'])
            except GitHubError as e:
                if e.status != 422 or not comments:
                    raise
                # A line GitHub won't accept: fall back to listing findings in the summary
                result['summary'] += '\n\n### Findings (could not be posted inline)\n' + '\n'.join(
                    f"- `{c['path']}:{c['line']}` {c['body'].splitlines()[0]}" for c in comments
                )
                result['inline_fallback'] = True
        self.client.upsert_issue_comment(number, result['summary'], SUMMARY_MARKER)
