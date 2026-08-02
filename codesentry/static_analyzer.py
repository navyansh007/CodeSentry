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
            'go_vet': [],
            'gofmt': [],
            'staticcheck': [],
            'clippy': [],
            'rubocop': [],
            'php_lint': [],
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

        go_files = by_ext.get('.go', [])
        if go_files:
            languages_present.append('go')
            print(f"Running Go static analysis on {len(go_files)} file(s)...")
            self._run_gofmt(go_files)
            self._run_go_vet(go_files)
            self._run_staticcheck(go_files)

        rust_files = by_ext.get('.rs', [])
        if rust_files:
            languages_present.append('rust')
            print(f"Running Rust static analysis on {len(rust_files)} file(s)...")
            self._run_clippy(rust_files)

        ruby_files = by_ext.get('.rb', [])
        if ruby_files:
            languages_present.append('ruby')
            print(f"Running Ruby static analysis on {len(ruby_files)} file(s)...")
            self._run_rubocop(ruby_files)

        php_files = by_ext.get('.php', [])
        if php_files:
            languages_present.append('php')
            print(f"Running PHP static analysis on {len(php_files)} file(s)...")
            self._run_php_lint(php_files)

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
    # Go
    # ---------------------------------------------------------------

    def _run_gofmt(self, files: List[str]) -> None:
        """Run gofmt -l to find files that aren't correctly formatted"""
        try:
            print("  Running gofmt...")
            cmd = ['gofmt', '-l'] + files
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            unformatted = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            self.results['gofmt'] = unformatted
            for file_path in unformatted:
                self._add_issue(
                    'gofmt', 'go', file_path, 0, 0, SEVERITY_WARNING,
                    'File is not gofmt-formatted', 'gofmt',
                )
        except subprocess.TimeoutExpired:
            print("    gofmt timeout - skipping")
        except FileNotFoundError:
            print("    gofmt not found - skipping (install the Go toolchain)")
        except Exception as e:
            print(f"    gofmt error: {str(e)}")

    def _run_go_vet(self, files: List[str]) -> None:
        """Run go vet per package directory (go vet operates on packages, not loose files)"""
        try:
            print("  Running go vet...")
            directories = sorted({os.path.dirname(f) or '.' for f in files})
            vet_issues = []

            for directory in directories:
                cmd = ['go', 'vet', './...']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=directory)
                for line in result.stderr.splitlines():
                    match = re.match(r'(.+\.go):(\d+):(\d+): (.+)', line.strip())
                    if match:
                        vet_issues.append({
                            'path': match.group(1),
                            'line': int(match.group(2)),
                            'column': int(match.group(3)),
                            'message': match.group(4),
                        })

            self.results['go_vet'] = vet_issues
            for issue in vet_issues:
                self._add_issue(
                    'go_vet', 'go', issue['path'], issue['line'], issue['column'],
                    SEVERITY_WARNING, issue['message'], 'go_vet',
                )
        except subprocess.TimeoutExpired:
            print("    go vet timeout - skipping")
        except FileNotFoundError:
            print("    go not found - skipping (install the Go toolchain)")
        except Exception as e:
            print(f"    go vet error: {str(e)}")

    def _run_staticcheck(self, files: List[str]) -> None:
        """Run staticcheck if installed (optional, more thorough than go vet)"""
        try:
            print("  Running staticcheck...")
            directories = sorted({os.path.dirname(f) or '.' for f in files})
            sc_issues = []

            for directory in directories:
                cmd = ['staticcheck', './...']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=directory)
                for line in result.stdout.splitlines():
                    match = re.match(r'(.+\.go):(\d+):(\d+): (.+)', line.strip())
                    if match:
                        sc_issues.append({
                            'path': match.group(1),
                            'line': int(match.group(2)),
                            'column': int(match.group(3)),
                            'message': match.group(4),
                        })

            self.results['staticcheck'] = sc_issues
            for issue in sc_issues:
                self._add_issue(
                    'staticcheck', 'go', issue['path'], issue['line'], issue['column'],
                    SEVERITY_WARNING, issue['message'], 'staticcheck',
                )
        except subprocess.TimeoutExpired:
            print("    staticcheck timeout - skipping")
        except FileNotFoundError:
            print("    staticcheck not found - skipping (optional, install from staticcheck.io)")
        except Exception as e:
            print(f"    staticcheck error: {str(e)}")

    # ---------------------------------------------------------------
    # Rust
    # ---------------------------------------------------------------

    def _run_clippy(self, files: List[str]) -> None:
        """Run cargo clippy (requires a Cargo.toml in the project)"""
        try:
            print("  Running cargo clippy...")
            file_set = {os.path.abspath(f) for f in files}
            cmd = ['cargo', 'clippy', '--message-format=json']
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300, cwd=self.project_path,
            )

            clippy_issues = []
            for line in result.stdout.splitlines():
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get('reason') != 'compiler-message':
                    continue
                message = msg.get('message', {})
                spans = message.get('spans', [])
                if not spans:
                    continue
                primary = next((s for s in spans if s.get('is_primary')), spans[0])
                file_path = os.path.abspath(os.path.join(self.project_path, primary.get('file_name', '')))
                if file_path not in file_set:
                    continue
                clippy_issues.append({
                    'path': file_path,
                    'line': primary.get('line_start', 0),
                    'column': primary.get('column_start', 0),
                    'level': message.get('level', 'warning'),
                    'message': message.get('message', ''),
                })

            self.results['clippy'] = clippy_issues
            for issue in clippy_issues:
                severity = SEVERITY_ERROR if issue['level'] == 'error' else SEVERITY_WARNING
                self._add_issue(
                    'clippy', 'rust', issue['path'], issue['line'], issue['column'],
                    severity, issue['message'], issue['level'],
                )
        except subprocess.TimeoutExpired:
            print("    cargo clippy timeout - skipping")
        except FileNotFoundError:
            print("    cargo not found - skipping (install the Rust toolchain)")
        except Exception as e:
            print(f"    cargo clippy error: {str(e)}")

    # ---------------------------------------------------------------
    # Ruby
    # ---------------------------------------------------------------

    def _run_rubocop(self, files: List[str]) -> None:
        """Run RuboCop"""
        try:
            print("  Running RuboCop...")
            cmd = ['rubocop', '--format=json'] + files
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            rubocop_issues = []
            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    for file_result in data.get('files', []):
                        file_path = file_result.get('path', '')
                        for offense in file_result.get('offenses', []):
                            rubocop_issues.append({
                                'path': file_path,
                                'line': offense.get('location', {}).get('line', 0),
                                'column': offense.get('location', {}).get('column', 0),
                                'severity': offense.get('severity', 'convention'),
                                'message': offense.get('message', ''),
                                'cop_name': offense.get('cop_name', ''),
                            })
                except json.JSONDecodeError:
                    pass

            self.results['rubocop'] = rubocop_issues
            for issue in rubocop_issues:
                if issue['severity'] in ('error', 'fatal'):
                    severity = SEVERITY_ERROR
                elif issue['severity'] == 'warning':
                    severity = SEVERITY_WARNING
                else:
                    severity = SEVERITY_INFO
                self._add_issue(
                    'rubocop', 'ruby', issue['path'], issue['line'], issue['column'],
                    severity, issue['message'], issue['cop_name'],
                )
        except subprocess.TimeoutExpired:
            print("    RuboCop timeout - skipping")
        except FileNotFoundError:
            print("    RuboCop not found - skipping (install with `gem install rubocop`)")
        except Exception as e:
            print(f"    RuboCop error: {str(e)}")

    # ---------------------------------------------------------------
    # PHP
    # ---------------------------------------------------------------

    def _run_php_lint(self, files: List[str]) -> None:
        """Run `php -l` (built into the PHP CLI) for syntax errors on each file"""
        try:
            print("  Running php -l...")
            lint_issues = []

            for file in files:
                cmd = ['php', '-l', file]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode != 0:
                    match = re.search(r'on line (\d+)', result.stdout + result.stderr)
                    line = int(match.group(1)) if match else 0
                    message = (result.stdout or result.stderr).strip().split('\n')[0]
                    lint_issues.append({'path': file, 'line': line, 'message': message})

            self.results['php_lint'] = lint_issues
            for issue in lint_issues:
                self._add_issue(
                    'php_lint', 'php', issue['path'], issue['line'], 0,
                    SEVERITY_ERROR, issue['message'], 'syntax',
                )
        except subprocess.TimeoutExpired:
            print("    php -l timeout - skipping")
        except FileNotFoundError:
            print("    php not found - skipping")
        except Exception as e:
            print(f"    php -l error: {str(e)}")

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
