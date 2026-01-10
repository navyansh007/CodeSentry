"""
Static Analysis Layer - Conventional linting and security checks
"""

import subprocess
import json
import os
from typing import List, Dict, Any
from pathlib import Path
import re


class StaticAnalyzer:
    """Performs static code analysis using various linting tools"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.results = {
            'pylint': [],
            'flake8': [],
            'bandit': [],
            'radon': [],
            'summary': {}
        }

    def analyze(self, files: List[str]) -> Dict[str, Any]:
        """Run all static analysis tools on the provided files"""
        python_files = [f for f in files if f.endswith('.py')]

        if not python_files:
            print("No Python files found for static analysis")
            return self.results

        print(f"Running static analysis on {len(python_files)} Python files...")

        # Run each analyzer
        self._run_pylint(python_files)
        self._run_flake8(python_files)
        self._run_bandit(python_files)
        self._run_radon(python_files)

        # Generate summary
        self._generate_summary()

        return self.results

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

            # Flake8 with json format plugin
            # Fallback to text parsing
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
                    self.results['bandit'] = bandit_data.get('results', [])
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

    def _generate_summary(self) -> None:
        """Generate summary statistics"""
        summary = {
            'total_issues': 0,
            'pylint_issues': len(self.results['pylint']),
            'flake8_issues': len(self.results['flake8']),
            'bandit_issues': len(self.results['bandit']),
            'high_complexity_functions': 0,
            'severity_breakdown': {
                'error': 0,
                'warning': 0,
                'info': 0,
                'security': 0
            }
        }

        # Count severity from pylint
        for issue in self.results['pylint']:
            issue_type = issue.get('type', '').lower()
            if issue_type in ['error', 'fatal']:
                summary['severity_breakdown']['error'] += 1
            elif issue_type == 'warning':
                summary['severity_breakdown']['warning'] += 1
            else:
                summary['severity_breakdown']['info'] += 1

        # Count severity from bandit
        summary['severity_breakdown']['security'] = len(self.results['bandit'])

        # Count high complexity functions
        for file_data in self.results['radon']:
            for file_path, functions in file_data.get('complexity', {}).items():
                for func in functions:
                    if func.get('complexity', 0) > 10:
                        summary['high_complexity_functions'] += 1

        summary['total_issues'] = (
            summary['pylint_issues'] +
            summary['flake8_issues'] +
            summary['bandit_issues']
        )

        self.results['summary'] = summary
