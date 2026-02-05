"""
HTML Report Generator - Creates GitHub PR-style code review reports
"""

import os
from datetime import datetime
from typing import Dict, Any
from jinja2 import Template
import markdown
from markdown.extensions import fenced_code, tables, nl2br, codehilite


class ReportGenerator:
    """Generates GitHub PR-style HTML reports for code reviews"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.output_dir = config['report']['output_dir']

        # Configure markdown parser
        self.md = markdown.Markdown(
            extensions=[
                'fenced_code',
                'tables',
                'nl2br',
                'codehilite',
                'toc'
            ],
            extension_configs={
                'codehilite': {
                    'css_class': 'highlight',
                    'linenums': False
                }
            }
        )

    def generate_report(
        self,
        static_results: Dict[str, Any],
        ai_results: Dict[str, Any],
        files_analyzed: list,
        project_path: str
    ) -> str:
        """Generate comprehensive HTML report"""
        print("\nGenerating HTML report...")

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"code_review_{timestamp}.html"
        output_path = os.path.join(self.output_dir, filename)

        # Render HTML
        html_content = self._render_html(
            static_results,
            ai_results,
            files_analyzed,
            project_path,
            timestamp
        )

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"Report generated: {output_path}")
        return output_path

    def _render_html(
        self,
        static_results: Dict[str, Any],
        ai_results: Dict[str, Any],
        files_analyzed: list,
        project_path: str,
        timestamp: str
    ) -> str:
        """Render HTML template"""

        # Convert markdown content to HTML
        ai_results_html = {
            'general_review': self._md_to_html(ai_results.get('general_review', '')),
            'architectural_insights': self._md_to_html(ai_results.get('architectural_insights', '')),
            'file_reviews': [
                {
                    'file': review['file'],
                    'review': self._md_to_html(review['review'])
                }
                for review in ai_results.get('file_reviews', [])
            ],
            'security_concerns': [
                {
                    'issue': concern['issue'],
                    'file': concern['file'],
                    'line': concern['line'],
                    'analysis': self._md_to_html(concern['analysis'])
                }
                for concern in ai_results.get('security_concerns', [])
            ],
            'best_practices': self._md_to_html('\n'.join(ai_results.get('best_practices', []))),
            'improvement_suggestions': ai_results.get('improvement_suggestions', [])
        }

        template = Template(self._get_template())

        return template.render(
            static_results=static_results,
            ai_results=ai_results_html,
            files_analyzed=files_analyzed,
            project_path=project_path,
            timestamp=timestamp,
            num_files=len(files_analyzed),
            datetime=datetime.now().strftime("%B %d, %Y at %H:%M:%S")
        )

    def _md_to_html(self, text: str) -> str:
        """Convert markdown to HTML"""
        if not text or not isinstance(text, str):
            return ""

        # Reset markdown parser
        self.md.reset()
        return self.md.convert(text)

    def _get_template(self) -> str:
        """Get GitHub PR-style HTML template"""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Review - {{ timestamp }}</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.5.0/github-markdown.min.css">
    <style>
        :root {
            --color-canvas-default: #ffffff;
            --color-canvas-subtle: #f6f8fa;
            --color-border-default: #d0d7de;
            --color-border-muted: #d8dee4;
            --color-neutral-muted: rgba(175,184,193,0.2);
            --color-accent-fg: #0969da;
            --color-accent-emphasis: #0969da;
            --color-danger-fg: #d1242f;
            --color-attention-fg: #9a6700;
            --color-success-fg: #1a7f37;
            --color-fg-default: #1f2328;
            --color-fg-muted: #656d76;
            --color-fg-subtle: #6e7781;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
            font-size: 14px;
            line-height: 1.5;
            color: var(--color-fg-default);
            background-color: var(--color-canvas-subtle);
        }

        .container {
            max-width: 1280px;
            margin: 0 auto;
            padding: 24px;
        }

        .pr-header {
            background: var(--color-canvas-default);
            border: 1px solid var(--color-border-default);
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 16px;
        }

        .pr-title {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--color-fg-default);
        }

        .pr-meta {
            display: flex;
            align-items: center;
            gap: 16px;
            color: var(--color-fg-muted);
            font-size: 14px;
        }

        .pr-meta-item {
            display: flex;
            align-items: center;
            gap: 4px;
        }

        .label {
            display: inline-block;
            padding: 0 7px;
            font-size: 12px;
            font-weight: 500;
            line-height: 18px;
            border-radius: 2em;
            border: 1px solid transparent;
        }

        .label-success {
            color: var(--color-success-fg);
            border-color: var(--color-success-fg);
        }

        .label-warning {
            color: var(--color-attention-fg);
            border-color: var(--color-attention-fg);
        }

        .label-danger {
            color: var(--color-danger-fg);
            border-color: var(--color-danger-fg);
        }

        .comment-box {
            background: var(--color-canvas-default);
            border: 1px solid var(--color-border-default);
            border-radius: 6px;
            margin-bottom: 16px;
            overflow: hidden;
        }

        .comment-header {
            padding: 16px;
            background: var(--color-canvas-subtle);
            border-bottom: 1px solid var(--color-border-default);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .comment-author {
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 600;
        }

        .bot-badge {
            background: var(--color-neutral-muted);
            border: 1px solid var(--color-border-default);
            border-radius: 2em;
            padding: 0 7px;
            font-size: 12px;
            font-weight: 500;
            color: var(--color-fg-muted);
        }

        .comment-body {
            padding: 16px;
        }

        .markdown-body {
            font-size: 14px;
        }

        .markdown-body h1 {
            font-size: 24px;
            font-weight: 600;
            padding-bottom: 8px;
            margin-top: 24px;
            margin-bottom: 16px;
            border-bottom: 1px solid var(--color-border-muted);
        }

        .markdown-body h2 {
            font-size: 20px;
            font-weight: 600;
            padding-bottom: 8px;
            margin-top: 24px;
            margin-bottom: 16px;
            border-bottom: 1px solid var(--color-border-muted);
        }

        .markdown-body h3 {
            font-size: 16px;
            font-weight: 600;
            margin-top: 24px;
            margin-bottom: 16px;
        }

        .markdown-body ul, .markdown-body ol {
            padding-left: 32px;
            margin-bottom: 16px;
        }

        .markdown-body li {
            margin-top: 4px;
        }

        .markdown-body p {
            margin-bottom: 16px;
        }

        .markdown-body code {
            background: var(--color-neutral-muted);
            padding: 2px 6px;
            border-radius: 6px;
            font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
            font-size: 85%;
        }

        .markdown-body pre {
            background: var(--color-canvas-subtle);
            padding: 16px;
            border-radius: 6px;
            overflow-x: auto;
            margin-bottom: 16px;
            border: 1px solid var(--color-border-default);
        }

        .markdown-body pre code {
            background: none;
            padding: 0;
            font-size: 12px;
            line-height: 1.45;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            margin: 16px 0;
        }

        .stat-card {
            background: var(--color-canvas-default);
            border: 1px solid var(--color-border-default);
            border-radius: 6px;
            padding: 16px;
            text-align: center;
        }

        .stat-value {
            font-size: 32px;
            font-weight: 600;
            color: var(--color-fg-default);
            line-height: 1;
        }

        .stat-label {
            font-size: 12px;
            color: var(--color-fg-muted);
            margin-top: 4px;
        }

        .issue-list {
            list-style: none;
            padding: 0;
        }

        .issue-item {
            padding: 12px 16px;
            border-bottom: 1px solid var(--color-border-muted);
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }

        .issue-item:last-child {
            border-bottom: none;
        }

        .issue-icon {
            flex-shrink: 0;
            width: 16px;
            height: 16px;
            margin-top: 2px;
        }

        .issue-content {
            flex: 1;
        }

        .issue-title {
            font-weight: 500;
            color: var(--color-fg-default);
            margin-bottom: 4px;
        }

        .issue-meta {
            font-size: 12px;
            color: var(--color-fg-muted);
            font-family: ui-monospace, monospace;
        }

        .section-divider {
            height: 8px;
            background: var(--color-canvas-subtle);
            margin: 24px 0;
            border-top: 1px solid var(--color-border-muted);
            border-bottom: 1px solid var(--color-border-muted);
        }

        .timeline {
            padding-left: 16px;
        }

        .timeline-item {
            position: relative;
            padding-left: 32px;
            padding-bottom: 24px;
        }

        .timeline-item::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 2px;
            background: var(--color-border-default);
        }

        .timeline-badge {
            position: absolute;
            left: -6px;
            top: 4px;
            width: 14px;
            height: 14px;
            border-radius: 50%;
            background: var(--color-canvas-default);
            border: 2px solid var(--color-accent-emphasis);
        }

        .file-header {
            background: var(--color-canvas-subtle);
            padding: 8px 16px;
            border-bottom: 1px solid var(--color-border-default);
            font-family: ui-monospace, monospace;
            font-size: 12px;
            color: var(--color-fg-default);
            font-weight: 600;
        }

        .security-alert {
            background: #fff8c5;
            border: 1px solid #d4a72c;
            border-left: 4px solid #d4a72c;
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 16px;
        }

        .security-alert-title {
            font-weight: 600;
            color: #9a6700;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .counter {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 20px;
            height: 20px;
            padding: 0 6px;
            font-size: 12px;
            font-weight: 600;
            line-height: 1;
            color: var(--color-fg-default);
            background-color: var(--color-neutral-muted);
            border-radius: 2em;
        }

        .flash {
            padding: 16px;
            margin-bottom: 16px;
            border: 1px solid transparent;
            border-radius: 6px;
        }

        .flash-success {
            background-color: #dafbe1;
            border-color: #2da44e;
            color: #1a7f37;
        }

        .flash-warning {
            background-color: #fff8c5;
            border-color: #d4a72c;
            color: #9a6700;
        }

        @media (max-width: 768px) {
            .container {
                padding: 12px;
            }

            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media print {
            body {
                background: white;
            }

            .container {
                max-width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- PR Header -->
        <div class="pr-header">
            <h1 class="pr-title">🛡️ CodeSentry Review Report</h1>
            <div class="pr-meta">
                <span class="pr-meta-item">
                    <strong>Project:</strong> {{ project_path }}
                </span>
                <span class="pr-meta-item">
                    <strong>Files:</strong> {{ num_files }}
                </span>
                <span class="pr-meta-item">
                    <strong>Date:</strong> {{ datetime }}
                </span>
            </div>
        </div>

        <!-- Summary Stats -->
        <div class="comment-box">
            <div class="comment-header">
                <div class="comment-author">
                    <span>📊 Analysis Summary</span>
                </div>
            </div>
            <div class="comment-body">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">{{ static_results.summary.total_issues }}</div>
                        <div class="stat-label">Total Issues</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{{ static_results.summary.severity_breakdown.error }}</div>
                        <div class="stat-label">Errors</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{{ static_results.summary.severity_breakdown.warning }}</div>
                        <div class="stat-label">Warnings</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{{ static_results.summary.severity_breakdown.security }}</div>
                        <div class="stat-label">Security Issues</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{{ static_results.summary.high_complexity_functions }}</div>
                        <div class="stat-label">High Complexity</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- AI General Review -->
        <div class="comment-box">
            <div class="comment-header">
                <div class="comment-author">
                    <span>🤖 CodeSentry AI</span>
                    <span class="bot-badge">Bot</span>
                </div>
                <span style="font-size: 12px; color: var(--color-fg-muted);">General Review</span>
            </div>
            <div class="comment-body">
                <div class="markdown-body">
                    {{ ai_results.general_review|safe }}
                </div>
            </div>
        </div>

        <!-- Architectural Insights -->
        <div class="comment-box">
            <div class="comment-header">
                <div class="comment-author">
                    <span>🏗️ CodeSentry AI</span>
                    <span class="bot-badge">Bot</span>
                </div>
                <span style="font-size: 12px; color: var(--color-fg-muted);">Architecture Analysis</span>
            </div>
            <div class="comment-body">
                <div class="markdown-body">
                    {{ ai_results.architectural_insights|safe }}
                </div>
            </div>
        </div>

        <!-- Security Concerns -->
        {% if ai_results.security_concerns %}
        <div class="comment-box">
            <div class="comment-header">
                <div class="comment-author">
                    <span>🔒 Security Analysis</span>
                    <span class="counter">{{ ai_results.security_concerns|length }}</span>
                </div>
            </div>
            <div class="comment-body">
                {% for concern in ai_results.security_concerns %}
                <div class="security-alert">
                    <div class="security-alert-title">
                        ⚠️ {{ concern.issue }}
                    </div>
                    <div style="font-size: 12px; color: var(--color-fg-muted); margin-bottom: 12px; font-family: monospace;">
                        {{ concern.file }}:{{ concern.line }}
                    </div>
                    <div class="markdown-body">
                        {{ concern.analysis|safe }}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}

        <!-- Static Analysis Results -->
        {% if static_results.pylint or static_results.flake8 %}
        <div class="comment-box">
            <div class="comment-header">
                <div class="comment-author">
                    <span>🔍 Static Analysis</span>
                    <span class="counter">{{ static_results.summary.total_issues }}</span>
                </div>
            </div>
            <div class="comment-body">
                {% if static_results.pylint %}
                <h3 style="margin-top: 0;">Pylint Issues</h3>
                <ul class="issue-list">
                    {% for issue in static_results.pylint[:20] %}
                    <li class="issue-item">
                        <span class="issue-icon">
                            {% if issue.type == 'error' %}🔴{% elif issue.type == 'warning' %}🟡{% else %}🔵{% endif %}
                        </span>
                        <div class="issue-content">
                            <div class="issue-title">{{ issue.message }}</div>
                            <div class="issue-meta">
                                {{ issue.path }}:{{ issue.line }}:{{ issue.column }} - {{ issue.symbol }}
                            </div>
                        </div>
                    </li>
                    {% endfor %}
                </ul>
                {% if static_results.pylint|length > 20 %}
                <p style="color: var(--color-fg-muted); font-style: italic; margin-top: 12px;">
                    ... and {{ static_results.pylint|length - 20 }} more issues
                </p>
                {% endif %}
                {% endif %}

                {% if static_results.flake8 %}
                <h3>Flake8 Issues</h3>
                <ul class="issue-list">
                    {% for issue in static_results.flake8[:15] %}
                    <li class="issue-item">
                        <span class="issue-icon">ℹ️</span>
                        <div class="issue-content">
                            <div class="issue-title">{{ issue.message }}</div>
                            <div class="issue-meta">
                                {{ issue.path }}:{{ issue.line }}:{{ issue.column }} - {{ issue.code }}
                            </div>
                        </div>
                    </li>
                    {% endfor %}
                </ul>
                {% endif %}
            </div>
        </div>
        {% endif %}

        <!-- File-Specific Reviews -->
        {% if ai_results.file_reviews %}
        <div class="comment-box">
            <div class="comment-header">
                <div class="comment-author">
                    <span>📄 File Reviews</span>
                    <span class="counter">{{ ai_results.file_reviews|length }}</span>
                </div>
            </div>
            <div class="comment-body">
                {% for review in ai_results.file_reviews %}
                <div style="{% if not loop.last %}margin-bottom: 24px; padding-bottom: 24px; border-bottom: 1px solid var(--color-border-muted);{% endif %}">
                    <div class="file-header">{{ review.file }}</div>
                    <div class="markdown-body" style="margin-top: 12px;">
                        {{ review.review|safe }}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}

        <!-- Best Practices -->
        {% if ai_results.best_practices %}
        <div class="comment-box">
            <div class="comment-header">
                <div class="comment-author">
                    <span>✅ Best Practices Review</span>
                </div>
            </div>
            <div class="comment-body">
                <div class="markdown-body">
                    {{ ai_results.best_practices|safe }}
                </div>
            </div>
        </div>
        {% endif %}

        <!-- Improvement Suggestions -->
        {% if ai_results.improvement_suggestions %}
        <div class="comment-box">
            <div class="comment-header">
                <div class="comment-author">
                    <span>💡 Improvement Suggestions</span>
                    <span class="counter">{{ ai_results.improvement_suggestions|length }}</span>
                </div>
            </div>
            <div class="comment-body">
                <ul class="issue-list">
                    {% for suggestion in ai_results.improvement_suggestions %}
                    <li class="issue-item">
                        <span class="issue-icon">✨</span>
                        <div class="issue-content">
                            <div class="issue-title">{{ suggestion }}</div>
                        </div>
                    </li>
                    {% endfor %}
                </ul>
            </div>
        </div>
        {% endif %}

        <!-- Footer -->
        <div style="text-align: center; padding: 24px; color: var(--color-fg-muted); font-size: 12px;">
            <p>
                Generated by <strong>CodeSentry</strong> •
                Powered by Qwen3-Coder with RAG Architecture •
                Report ID: {{ timestamp }}
            </p>
        </div>
    </div>
</body>
</html>
"""
