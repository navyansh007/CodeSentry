"""
Structured Findings - A typed, validated shape for AI review comments

Free-form markdown reviews can't be filtered, deduplicated, verified or
posted as inline PR comments. Every AI finding is therefore parsed into a
`Finding` with a file, line, severity, category, confidence and an
`evidence` snippet quoted from the code, so the guardrail pipeline can
reason about it deterministically.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

SEVERITIES = ('critical', 'major', 'minor', 'nit')
CATEGORIES = (
    'bug', 'security', 'performance', 'logic', 'error_handling',
    'maintainability', 'design', 'style', 'documentation', 'testing',
)

# Higher = more important; used to rank findings when caps apply
SEVERITY_RANK = {'critical': 4, 'major': 3, 'minor': 2, 'nit': 1}

_SEVERITY_ALIASES = {
    'high': 'major', 'blocker': 'critical', 'error': 'major',
    'medium': 'minor', 'warning': 'minor', 'moderate': 'minor',
    'low': 'nit', 'info': 'nit', 'trivial': 'nit', 'suggestion': 'nit',
}


@dataclass
class Finding:
    """A single, structured review comment"""

    file: str
    line: int
    title: str
    body: str = ''
    severity: str = 'minor'
    category: str = 'maintainability'
    confidence: float = 0.5
    evidence: str = ''
    suggestion: str = ''
    end_line: Optional[int] = None
    source: str = 'ai'
    verdict: Optional[str] = None
    verdict_reason: str = ''
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        """Stable id used for dedupe and idempotent PR comments (ignores line drift)"""
        normalized_title = re.sub(r'\W+', ' ', self.title.lower()).strip()
        raw = f"{self.file}|{self.category}|{normalized_title}"
        return hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]

    @property
    def priority(self) -> float:
        return SEVERITY_RANK.get(self.severity, 1) * self.confidence

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['fingerprint'] = self.fingerprint
        return data

    def to_markdown(self) -> str:
        badge = {
            'critical': '🔴 Critical', 'major': '🟠 Major',
            'minor': '🟡 Minor', 'nit': '🔵 Nit',
        }.get(self.severity, self.severity)
        parts = [f"**{badge} · {self.category}** — {self.title}"]
        if self.body:
            parts.append(self.body)
        if self.suggestion:
            parts.append(f"**Suggestion:**\n```\n{self.suggestion}\n```")
        return '\n\n'.join(parts)


def _normalize_severity(value: Any) -> str:
    value = str(value or '').strip().lower()
    if value in SEVERITIES:
        return value
    return _SEVERITY_ALIASES.get(value, 'minor')


def _normalize_category(value: Any) -> str:
    value = str(value or '').strip().lower().replace(' ', '_').replace('-', '_')
    if value in CATEGORIES:
        return value
    if 'secur' in value or 'vuln' in value:
        return 'security'
    if 'perf' in value:
        return 'performance'
    if 'doc' in value or 'comment' in value:
        return 'documentation'
    if 'test' in value:
        return 'testing'
    if 'error' in value or 'exception' in value:
        return 'error_handling'
    if 'naming' in value or 'format' in value or 'lint' in value:
        return 'style'
    return 'maintainability'


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip().split('-')[0])
    except (TypeError, ValueError):
        return default


def _to_confidence(value: Any) -> float:
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return 0.5
    if conf > 1:  # model answered on a 0-100 or 1-10 scale
        conf = conf / 100 if conf > 10 else conf / 10
    return max(0.0, min(1.0, conf))


def extract_json(text: str) -> Optional[Any]:
    """
    Pull the first JSON object/array out of an LLM response.

    Handles ```json fenced blocks, leading prose, and trailing commentary,
    which every provider produces from time to time.
    """
    if not text or not isinstance(text, str):
        return None

    # Reasoning models (Qwen3, DeepSeek-R1, gpt-oss, ...) may prepend a
    # <think> block whose braces would otherwise be mistaken for the answer
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)

    candidates = re.findall(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
    candidates.append(text)

    for candidate in candidates:
        candidate = candidate.strip()
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            pass

        # Fall back to the outermost {...} or [...] span
        for opener, closer in (('{', '}'), ('[', ']')):
            start = candidate.find(opener)
            end = candidate.rfind(closer)
            if start != -1 and end > start:
                try:
                    return json.loads(candidate[start:end + 1])
                except (json.JSONDecodeError, ValueError):
                    continue
    return None


def parse_findings(response: str, default_file: str) -> Optional[List[Finding]]:
    """
    Parse an LLM response into Findings.

    Returns None if no JSON could be recovered (so the caller can retry),
    and an empty list when the model explicitly reported no issues.
    """
    data = extract_json(response)
    if data is None:
        return None

    if isinstance(data, dict):
        raw_findings = data.get('findings', data.get('comments', data.get('issues', [])))
    elif isinstance(data, list):
        raw_findings = data
    else:
        return None

    if not isinstance(raw_findings, list):
        return None

    findings = []
    for raw in raw_findings:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get('title') or raw.get('summary') or raw.get('message') or '').strip()
        if not title:
            continue
        line = _to_int(raw.get('line', raw.get('start_line')), 0)
        end_line = raw.get('end_line')
        findings.append(Finding(
            file=str(raw.get('file') or default_file),
            line=line,
            end_line=_to_int(end_line, line) if end_line is not None else None,
            title=title[:200],
            body=str(raw.get('body') or raw.get('explanation') or raw.get('description') or '').strip(),
            severity=_normalize_severity(raw.get('severity')),
            category=_normalize_category(raw.get('category') or raw.get('type')),
            confidence=_to_confidence(raw.get('confidence')),
            evidence=str(raw.get('evidence') or raw.get('code') or '').strip(),
            suggestion=str(raw.get('suggestion') or raw.get('fix') or '').strip(),
        ))
    return findings


FINDINGS_SCHEMA_PROMPT = """Respond with ONLY a JSON object, no prose, in exactly this shape:
{
  "verdict": "LGTM" | "NEEDS_CHANGES",
  "findings": [
    {
      "line": <int, 1-based line number in the file>,
      "end_line": <int, optional>,
      "title": "<one-line summary>",
      "body": "<why this is a problem and its impact>",
      "severity": "critical" | "major" | "minor" | "nit",
      "category": "bug" | "security" | "performance" | "logic" | "error_handling" | "maintainability" | "design" | "style" | "documentation" | "testing",
      "confidence": <float 0.0-1.0, how sure you are this is a real problem>,
      "evidence": "<the exact line(s) of code this refers to, copied verbatim>",
      "suggestion": "<replacement code or concrete fix, optional>"
    }
  ]
}
If the code is correct, follows good practice, and there is no materially better approach, return {"verdict": "LGTM", "findings": []}.
Never invent issues to fill the list. Every finding MUST quote real code in "evidence"."""
