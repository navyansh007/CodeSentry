"""
Static Analysis Layer - Multi-language linting, security, and complexity checks

Each language runs whichever of its tools are installed on PATH; a missing
tool is skipped with a message rather than failing the run, the same way the
original Python-only analyzer behaved. Every tool's raw output is normalized
into a common issue shape (file/line/column/severity/message/tool/language)
so scoring and the rule engine can reason about the whole codebase at once,
regardless of which languages it's written in.
"""

import subprocess
import json
import os
from typing import List, Dict, Any, Optional
import re

SEVERITY_ERROR = 'error'
SEVERITY_WARNING = 'warning'
SEVERITY_INFO = 'info'
SEVERITY_SECURITY = 'security'


class StaticAnalyzer:
    """Performs static code analysis across multiple languages"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.results = {
            'pylint': [],
            'flake8': [],
            'bandit': [],
            'radon': [],
            'eslint': [],
            'issues': [],
            'languages_analyzed': [],
            'summary': {},
        }

    def analyze(self, files: List[str], project_path: Optional[str] = None) -> Dict[str, Any]:
        """Run all applicable static analysis tools on the provided files"""
        self.project_path = project_path or (os.path.commonpath(files) if files else '.')

        by_ext = self._group_by_extension(files)
        languages_present = []

        python_files = by_ext.get('.py', [])
        if python_files:
            languages_present.append('python')
            print(f"Running Python static analysis on {len(python_files)} file(s)...")
            self._run_pylint(python_files)
            self._run_flake8(python_files)
            self._run_bandit(python_files)
            self._run_radon(python_files)

        js_files = sum((by_ext.get(ext, []) for ext in ('.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx')), [])
        if js_files:
            languages_present.append('javascript/typescript')
            print(f"Running JavaScript/TypeScript static analysis on {len(js_files)} file(s)...")
            self._run_eslint(js_files)

        if not languages_present:
            print("No supported source files found for static analysis")

        self.results['languages_analyzed'] = languages_present
        self._generate_summary()

        return self.results

    @staticmethod
    def _group_by_extension(files: List[str]) -> Dict[str, List[str]]:
        grouped: Dict[str, List[str]] = {}
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            grouped.setdefault(ext, []).append(f)
        return grouped

    def _add_issue(self, tool: str, language: str, file: str, line: Any, column: Any,
                    severity: str, message: str, code: str = '') -> None:
        self.results['issues'].append({
            'tool': tool,
            'language': language,
            'file': file,
            'line': line or 0,
            'column': column or 0,
            'severity': severity,
            'message': message,
            'code': code,
        })

    # ---------------------------------------------------------------
    # Python
    # ---------------------------------------------------------------

    def _run_pylint(self, files: List[str]) -> None:
        """Run Pylint analysis"""
        try:
            print("  Running Pylint...")
            cmd = ['pylint', '--output-format=json', '--exit-zero'] + files
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.stdout:
                try:
                    pylint_data = json.loads(result.stdout)
                    self.results['pylint'] = pylint_data
                    for issue in pylint_data:
                        issue_type = issue.get('type', '').lower()
                        if issue_type in ('error', 'fatal'):
                            severity = SEVERITY_ERROR
                        elif issue_type == 'warning':
                            severity = SEVERITY_WARNING
                        else:
                            severity = SEVERITY_INFO
                        self._add_issue(
                            'pylint', 'python', issue.get('path', ''), issue.get('line'),
                            issue.get('column'), severity, issue.get('message', ''),
                            issue.get('symbol', ''),
                        )
                except json.JSONDecodeError:
                    self.results['pylint'] = []
        except subprocess.TimeoutExpired:
            print("    Pylint timeout - skipping")
        except FileNotFoundError:
            print("    Pylint not found - skipping")
        except Exception as e:
            print(f"    Pylint error: {str(e)}")

    def _run_flake8(self, files: List[str]) -> None:
        """Run Flake8 analysis"""
        try:
            print("  Running Flake8...")
            cmd = ['flake8', '--format=json'] + files
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            flake8_issues = []
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        match = re.match(r'(.+):(\d+):(\d+): ([A-Z]\d+) (.+)', line)
                        if match:
                            flake8_issues.append({
                                'path': match.group(1),
                                'line': int(match.group(2)),
                                'column': int(match.group(3)),
                                'code': match.group(4),
                                'message': match.group(5)
                            })

            self.results['flake8'] = flake8_issues
            for issue in flake8_issues:
                code = issue['code']
                # F82x = undefined names, E9xx = syntax errors: treat as real errors
                if code.startswith('F82') or code.startswith('E9'):
                    severity = SEVERITY_ERROR
                else:
                    severity = SEVERITY_WARNING
                self._add_issue(
                    'flake8', 'python', issue['path'], issue['line'], issue['column'],
                    severity, issue['message'], code,
                )
        except subprocess.TimeoutExpired:
            print("    Flake8 timeout - skipping")
        except FileNotFoundError:
            print("    Flake8 not found - skipping")
        except Exception as e:
            print(f"    Flake8 error: {str(e)}")

    def _run_bandit(self, files: List[str]) -> None:
        """Run Bandit security analysis"""
        try:
            print("  Running Bandit (security)...")
            cmd = ['bandit', '-f', 'json', '-r'] + files
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.stdout:
                try:
                    bandit_data = json.loads(result.stdout)
                    bandit_results = bandit_data.get('results', [])
                    self.results['bandit'] = bandit_results
                    for issue in bandit_results:
                        # Bandit's LOW-severity findings are mostly noise (e.g. "subprocess
                        # module used") rather than real vulnerabilities, so only
                        # MEDIUM/HIGH count toward the security bucket - LOW still gets
                        # surfaced, just as a regular warning.
                        bandit_severity = (issue.get('issue_severity') or '').upper()
                        severity = SEVERITY_SECURITY if bandit_severity in ('MEDIUM', 'HIGH') else SEVERITY_WARNING
                        self._add_issue(
                            'bandit', 'python', issue.get('filename', ''), issue.get('line_number'),
                            0, severity, issue.get('issue_text', ''),
                            issue.get('test_id', ''),
                        )
                except json.JSONDecodeError:
                    self.results['bandit'] = []
        except subprocess.TimeoutExpired:
            print("    Bandit timeout - skipping")
        except FileNotFoundError:
            print("    Bandit not found - skipping")
        except Exception as e:
            print(f"    Bandit error: {str(e)}")

    def _run_radon(self, files: List[str]) -> None:
        """Run Radon complexity analysis"""
        try:
            print("  Running Radon (complexity)...")
            complexity_results = []

            for file in files:
                cmd = ['radon', 'cc', '-j', file]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.stdout:
                    try:
                        radon_data = json.loads(result.stdout)
                        complexity_results.append({
                            'file': file,
                            'complexity': radon_data
                        })
                    except json.JSONDecodeError:
                        pass

            self.results['radon'] = complexity_results
        except subprocess.TimeoutExpired:
            print("    Radon timeout - skipping")
        except FileNotFoundError:
            print("    Radon not found - skipping")
        except Exception as e:
            print(f"    Radon error: {str(e)}")

    # ---------------------------------------------------------------
    # JavaScript / TypeScript
    # ---------------------------------------------------------------

    def _run_eslint(self, files: List[str]) -> None:
        """Run ESLint (requires an ESLint config in the target project)"""
        try:
            print("  Running ESLint...")
            cmd = ['eslint', '--format=json'] + files
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.stdout:
                try:
                    eslint_data = json.loads(result.stdout)
                    self.results['eslint'] = eslint_data
                    for file_result in eslint_data:
                        file_path = file_result.get('filePath', '')
                        for msg in file_result.get('messages', []):
                            severity = SEVERITY_ERROR if msg.get('severity') == 2 else SEVERITY_WARNING
                            self._add_issue(
                                'eslint', 'javascript', file_path, msg.get('line'),
                                msg.get('column'), severity, msg.get('message', ''),
                                msg.get('ruleId') or '',
                            )
                except json.JSONDecodeError:
                    self.results['eslint'] = []
        except subprocess.TimeoutExpired:
            print("    ESLint timeout - skipping")
        except FileNotFoundError:
            print("    ESLint not found - skipping (install with `npm i -g eslint`)")
        except Exception as e:
            print(f"    ESLint error: {str(e)}")

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------

    def _generate_summary(self) -> None:
        """Generate summary statistics from the unified issues list"""
        issues = self.results['issues']

        severity_breakdown = {
            SEVERITY_ERROR: 0,
            SEVERITY_WARNING: 0,
            SEVERITY_INFO: 0,
            SEVERITY_SECURITY: 0,
        }
        by_tool: Dict[str, int] = {}
        by_language: Dict[str, int] = {}

        for issue in issues:
            severity_breakdown[issue['severity']] = severity_breakdown.get(issue['severity'], 0) + 1
            by_tool[issue['tool']] = by_tool.get(issue['tool'], 0) + 1
            by_language[issue['language']] = by_language.get(issue['language'], 0) + 1

        high_complexity_functions = 0
        for file_data in self.results['radon']:
            for file_path, functions in file_data.get('complexity', {}).items():
                for func in functions:
                    if func.get('complexity', 0) > 10:
                        high_complexity_functions += 1

        self.results['summary'] = {
            'total_issues': len(issues),
            'pylint_issues': len(self.results['pylint']),
            'flake8_issues': len(self.results['flake8']),
            'bandit_issues': len(self.results['bandit']),
            'high_complexity_functions': high_complexity_functions,
            'severity_breakdown': severity_breakdown,
            'issues_by_tool': by_tool,
            'issues_by_language': by_language,
            'languages_analyzed': self.results['languages_analyzed'],
        }
