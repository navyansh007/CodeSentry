"""
Finding Critic - Falsification-first verification of AI review comments

Two recent results shape this module:

* OpenCodeReview (arXiv:2608.09290) uses a reflection step that only
  *filters* and never generates, and whose reflector sees only the code -
  not the reviewing agent's own reasoning - to avoid the self-reinforcing
  bias of intrinsic self-critique. It keeps precision high as comment volume
  grows.
* Adversarial Review (arXiv:2608.18167) pairs the reviewer with a critic
  that is explicitly asked to disagree, so only findings that survive a
  structured challenge reach the developer.

The critic therefore receives each claim stripped down to "file, line,
claim, quoted code", plus the surrounding code, and is asked to *refute* it.
REFUTED findings are dropped; UNCERTAIN ones are kept with reduced
confidence (or dropped, if configured). It can never add new findings.
"""

import os
from typing import Any, Callable, Dict, List, Tuple

from .findings import Finding, extract_json
from .guardrails import UNTRUSTED_PREAMBLE, fence_untrusted, DROP_REFUTED

UPHELD = 'UPHELD'
REFUTED = 'REFUTED'
UNCERTAIN = 'UNCERTAIN'


class FindingCritic:
    """Asks the LLM to falsify each finding; keeps only those that survive"""

    PROMPT = """You are a skeptical senior engineer verifying claims made by another code reviewer.
Your job is to REFUTE each claim if the code shows it is wrong, irrelevant, already handled, or speculative.
Only answer UPHELD when the code itself clearly demonstrates the problem.

{preamble}

File: {file}
{code}

Claims to verify:
{claims}

For each claim, respond with ONLY JSON:
{{"verdicts": [{{"id": <claim id>, "verdict": "UPHELD" | "REFUTED" | "UNCERTAIN", "reason": "<one sentence citing the code>"}}]}}"""

    def __init__(self, config: Dict[str, Any], llm_call: Callable[[str], str]):
        cfg = (config.get('guardrails', {}) or {}).get('critic', {}) or {}
        self.enabled = cfg.get('enabled', True)
        self.drop_uncertain = cfg.get('drop_uncertain', False)
        self.uncertain_penalty = float(cfg.get('uncertain_confidence_penalty', 0.15))
        self.context_lines = int(cfg.get('context_lines', 15))
        self.max_claims_per_call = int(cfg.get('max_claims_per_call', 8))
        self.llm_call = llm_call

    def verify(self, findings: List[Finding], file_lines: Dict[str, List[str]],
               redact: Callable[[str], str] = None) -> Tuple[List[Finding], List[Tuple[Finding, str]]]:
        """Return (kept, dropped) after critic review. Guardrail findings pass through."""
        if not self.enabled or not findings:
            return findings, []

        kept: List[Finding] = []
        dropped: List[Tuple[Finding, str]] = []

        by_file: Dict[str, List[Finding]] = {}
        for finding in findings:
            if finding.source.startswith('guardrail'):
                kept.append(finding)
            else:
                by_file.setdefault(finding.file, []).append(finding)

        for file_path, file_findings in by_file.items():
            lines = file_lines.get(file_path, [])
            for start in range(0, len(file_findings), self.max_claims_per_call):
                batch = file_findings[start:start + self.max_claims_per_call]
                verdicts = self._ask(file_path, batch, lines, redact)
                for idx, finding in enumerate(batch):
                    verdict, reason = verdicts.get(idx, (UNCERTAIN, 'critic gave no verdict'))
                    finding.verdict = verdict
                    finding.verdict_reason = reason
                    if verdict == REFUTED:
                        dropped.append((finding, DROP_REFUTED))
                    elif verdict == UNCERTAIN and self.drop_uncertain:
                        dropped.append((finding, DROP_REFUTED))
                    else:
                        if verdict == UNCERTAIN:
                            finding.confidence = max(0.0, round(finding.confidence - self.uncertain_penalty, 2))
                        kept.append(finding)

        return kept, dropped

    def _ask(self, file_path: str, batch: List[Finding], lines: List[str],
             redact: Callable[[str], str]) -> Dict[int, Tuple[str, str]]:
        claims = []
        for idx, f in enumerate(batch):
            # Deliberately omit the reviewer's explanation and confidence
            claims.append(
                f"[{idx}] line {f.line}: {f.title}\n    quoted code: {f.evidence.strip()[:300] or '(none)'}"
            )

        code = self._excerpt(batch, lines)
        if redact:
            code = redact(code)

        prompt = self.PROMPT.format(
            preamble=UNTRUSTED_PREAMBLE,
            file=file_path,
            code=fence_untrusted(code, os.path.basename(file_path)),
            claims='\n'.join(claims),
        )
        response = self.llm_call(prompt)
        data = extract_json(response) if isinstance(response, str) else None

        verdicts: Dict[int, Tuple[str, str]] = {}
        if isinstance(data, dict):
            items = data.get('verdicts', [])
        elif isinstance(data, list):
            items = data
        else:
            # Critic unavailable: fail open (keep findings) but mark them
            return {idx: (UNCERTAIN, 'critic unavailable') for idx in range(len(batch))}

        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            try:
                idx = int(item.get('id'))
            except (TypeError, ValueError):
                continue
            if not 0 <= idx < len(batch):
                continue  # the critic may not invent claims
            verdict = str(item.get('verdict', UNCERTAIN)).upper()
            if verdict not in (UPHELD, REFUTED, UNCERTAIN):
                verdict = UNCERTAIN
            verdicts[idx] = (verdict, str(item.get('reason', '')).strip()[:300])
        return verdicts

    def _excerpt(self, batch: List[Finding], lines: List[str]) -> str:
        """Numbered code windows around every claim, merged when they overlap"""
        if not lines:
            return '\n'.join(f.evidence for f in batch)
        windows = []
        for f in batch:
            start = max(1, f.line - self.context_lines)
            end = min(len(lines), (f.end_line or f.line) + self.context_lines)
            windows.append([start, end])
        windows.sort()
        merged = [windows[0]]
        for start, end in windows[1:]:
            if start <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        parts = []
        for start, end in merged:
            parts.append('\n'.join(f'{n:>5} | {lines[n - 1]}' for n in range(start, end + 1)))
        return '\n   ...\n'.join(parts)
