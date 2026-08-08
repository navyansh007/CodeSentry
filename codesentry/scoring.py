"""
Quality Scoring - Converts static analysis findings into a single 0-100 score

The score is deterministic and based only on static analysis output, so it
works the same whether or not the AI layer (`--no-ai`) ran, which matters
for the rule engine / CI exit codes.
"""

from typing import Any, Dict

DEFAULT_WEIGHTS = {
    'error': 5,
    'security': 8,
    'warning': 2,
    'info': 0.25,
    'high_complexity': 3,
}

DEFAULT_GRADE_BANDS = {
    'A': 90,
    'B': 80,
    'C': 70,
    'D': 60,
    'F': 0,
}


class QualityScorer:
    """Computes a 0-100 code quality score from static analysis results"""

    def __init__(self, config: Dict[str, Any]):
        scoring_cfg = config.get('scoring', {}) or {}
        self.enabled = scoring_cfg.get('enabled', True)
        self.base_score = scoring_cfg.get('base_score', 100)
        self.weights = {**DEFAULT_WEIGHTS, **(scoring_cfg.get('weights') or {})}
        self.grade_bands = {**DEFAULT_GRADE_BANDS, **(scoring_cfg.get('grade_bands') or {})}

    def calculate(self, static_results: Dict[str, Any], num_files: int) -> Dict[str, Any]:
        """Calculate the quality score and a breakdown of what drove it"""
        summary = static_results.get('summary', {}) or {}
        severity = summary.get('severity_breakdown', {}) or {}
        num_files = max(num_files, 1)

        counts = {
            'error': severity.get('error', 0),
            'security': severity.get('security', 0),
            'warning': severity.get('warning', 0),
            'info': severity.get('info', 0),
            'high_complexity': summary.get('high_complexity_functions', 0),
        }

        deductions = {
            category: round(count * self.weights.get(category, 0), 2)
            for category, count in counts.items()
        }
        total_deduction = sum(deductions.values())

        # Normalize to a per-file average so the score reflects issue
        # *density* rather than raw count - otherwise a 500-file monorepo
        # would always score worse than a 5-file script at the same level
        # of code quality, just because it has more files to find issues in.
        normalized_deduction = total_deduction / num_files

        score = max(0.0, min(100.0, self.base_score - normalized_deduction))
        score = round(score, 1)

        return {
            'score': score,
            'grade': self._grade(score),
            'counts': counts,
            'deductions': deductions,
            'total_deduction': round(total_deduction, 2),
            'normalized_deduction': round(normalized_deduction, 2),
            'files_analyzed': num_files,
        }

    def _grade(self, score: float) -> str:
        for grade in ('A', 'B', 'C', 'D'):
            if score >= self.grade_bands.get(grade, DEFAULT_GRADE_BANDS[grade]):
                return grade
        return 'F'
