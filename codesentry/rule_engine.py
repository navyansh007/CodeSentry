"""
Rule Engine - Evaluates user-defined pass/fail policy against review metrics

Rules are declared in config.yaml under `rules.conditions`. Each rule
compares a metric (e.g. `score`, `security_issues`) against a value using an
operator. A `severity: fail` rule that doesn't hold makes the overall run
fail (non-zero exit code, useful for CI gates); `severity: warn` rules are
reported but never fail the run.
"""

import operator as op
from typing import Any, Dict, List

_OPERATORS = {
    '>=': op.ge,
    '<=': op.le,
    '==': op.eq,
    '!=': op.ne,
    '>': op.gt,
    '<': op.lt,
}


class RuleEngineError(Exception):
    """Raised when a rule is malformed"""


class RuleEngine:
    """Evaluates configured rules against a metrics dict"""

    def __init__(self, config: Dict[str, Any]):
        rules_cfg = config.get('rules', {}) or {}
        self.enabled = rules_cfg.get('enabled', False)
        self.conditions = rules_cfg.get('conditions', []) or []

    def evaluate(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate every configured rule against `metrics`.

        Returns {'passed': bool, 'results': [...]}. `passed` is False only if
        at least one `severity: fail` rule doesn't hold; `severity: warn`
        rules never affect it.
        """
        results: List[Dict[str, Any]] = []
        overall_passed = True

        if not self.enabled:
            return {'passed': True, 'results': results, 'enabled': False}

        for rule in self.conditions:
            name = rule.get('name', 'Unnamed rule')
            metric_name = rule.get('metric')
            operator_symbol = rule.get('operator', '>=')
            expected_value = rule.get('value')
            severity = rule.get('severity', 'fail')

            if metric_name is None or expected_value is None:
                raise RuleEngineError(f"Rule '{name}' is missing a 'metric' or 'value'")

            comparator = _OPERATORS.get(operator_symbol)
            if comparator is None:
                raise RuleEngineError(
                    f"Rule '{name}' uses unsupported operator '{operator_symbol}'. "
                    f"Supported operators: {', '.join(_OPERATORS.keys())}"
                )

            if metric_name not in metrics:
                raise RuleEngineError(
                    f"Rule '{name}' references unknown metric '{metric_name}'. "
                    f"Available metrics: {', '.join(sorted(metrics.keys()))}"
                )

            actual_value = metrics[metric_name]
            rule_passed = comparator(actual_value, expected_value)

            if not rule_passed and severity == 'fail':
                overall_passed = False

            results.append({
                'name': name,
                'metric': metric_name,
                'operator': operator_symbol,
                'expected': expected_value,
                'actual': actual_value,
                'passed': rule_passed,
                'severity': severity,
            })

        return {'passed': overall_passed, 'results': results, 'enabled': True}

    @staticmethod
    def build_metrics(score_result: Dict[str, Any], static_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Build the metrics dict rules can reference, from scoring + static analysis output"""
        severity = static_summary.get('severity_breakdown', {}) or {}
        return {
            'score': score_result.get('score', 0),
            'total_issues': static_summary.get('total_issues', 0),
            'error_issues': severity.get('error', 0),
            'warning_issues': severity.get('warning', 0),
            'info_issues': severity.get('info', 0),
            'security_issues': severity.get('security', 0),
            'high_complexity_functions': static_summary.get('high_complexity_functions', 0),
        }
