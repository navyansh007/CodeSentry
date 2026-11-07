"""
`codesentry-pr` - Review a GitHub pull request and post inline comments

Inside GitHub Actions the repository and PR number are read from the
environment (GITHUB_REPOSITORY / GITHUB_EVENT_PATH), so the command needs
no arguments there. Locally:

    export GITHUB_TOKEN=...   # needs pull-requests: write
    codesentry-pr --repo owner/name --pr 42 --dry-run
"""

import json
import os
import sys
from pathlib import Path

import click
from colorama import Fore, Style, init

from .github_client import DEFAULT_API_URL, GitHubClient, GitHubError
from .pr_reviewer import PRReviewer
from .utils import load_config

init(autoreset=True)


def detect_pr_number() -> int:
    """PR number from the GitHub Actions event payload, or 0 if unavailable"""
    event_path = os.getenv('GITHUB_EVENT_PATH')
    if not event_path or not os.path.exists(event_path):
        return 0
    try:
        with open(event_path, 'r', encoding='utf-8') as fh:
            event = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return 0
    pr = event.get('pull_request') or {}
    if pr.get('number'):
        return int(pr['number'])
    # issue_comment events on PRs (e.g. a "/codesentry" comment trigger)
    issue = event.get('issue') or {}
    if issue.get('pull_request') and issue.get('number'):
        return int(issue['number'])
    return 0


def resolve_config_path(config: str) -> str:
    if os.path.exists(config):
        return config
    bundled = Path(__file__).parent.parent / 'config.yaml'
    return str(bundled)


@click.command()
@click.option('--repo', default=lambda: os.getenv('GITHUB_REPOSITORY', ''),
              help='Repository as owner/name (default: $GITHUB_REPOSITORY)')
@click.option('--pr', 'pr_number', type=int, default=0,
              help='Pull request number (default: read from the GitHub Actions event)')
@click.option('--config', '-c', default='config.yaml', help='Path to configuration file')
@click.option('--token-env', default='GITHUB_TOKEN', help='Env var holding the GitHub token')
@click.option('--api-url', default=lambda: os.getenv('GITHUB_API_URL', DEFAULT_API_URL),
              help='GitHub API URL (set for GitHub Enterprise Server)')
@click.option('--provider', default=None, help='LLM provider override')
@click.option('--model', default=None, help='LLM model override')
@click.option('--no-ai', is_flag=True, help='Static analysis and guardrail checks only')
@click.option('--dry-run', is_flag=True, help='Print the review instead of posting it')
@click.option('--no-fail-on-rules', is_flag=True, help='Exit 0 even if a blocking rule fails')
@click.option('--json-output', type=click.Path(), default=None, help='Also write the result as JSON')
def main(repo, pr_number, config, token_env, api_url, provider, model, no_ai, dry_run,
         no_fail_on_rules, json_output):
    """Review a GitHub pull request with CodeSentry and post inline comments."""
    pr_number = pr_number or detect_pr_number()
    if not pr_number:
        click.echo(f"{Fore.RED}Error: no PR number given and none found in GITHUB_EVENT_PATH{Style.RESET_ALL}")
        sys.exit(2)

    cfg = load_config(resolve_config_path(config))
    if provider:
        cfg['llm']['provider'] = provider
    if model:
        cfg['llm']['model'] = model

    try:
        client = GitHubClient(os.getenv(token_env, ''), repo, api_url=api_url)
    except GitHubError as e:
        click.echo(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        sys.exit(2)

    click.echo(f"{Fore.CYAN}🛡️  CodeSentry reviewing {repo}#{pr_number}"
               f"{' (dry run)' if dry_run else ''}{Style.RESET_ALL}")

    try:
        result = PRReviewer(cfg, client, use_ai=not no_ai).run(pr_number, dry_run=dry_run)
    except GitHubError as e:
        click.echo(f"{Fore.RED}GitHub API error: {e}{Style.RESET_ALL}")
        if e.status in (401, 403):
            click.echo("Check that the token has 'pull-requests: write' and 'contents: read' permissions.")
        sys.exit(2)

    if result.get('status') == 'skipped':
        click.echo(f"{Fore.YELLOW}Skipped: {result['reason']}{Style.RESET_ALL}")
        sys.exit(0)

    click.echo(f"  Files reviewed: {len(result['files'])} · findings: {len(result['findings'])} "
               f"· new inline comments: {len(result['comments'])} · event: {result['event']}")

    if dry_run:
        click.echo('\n' + result['summary'])
        for c in result['comments']:
            click.echo(f"\n--- {c['path']}:{c['line']}\n{c['body']}")
    else:
        click.echo(f"{Fore.GREEN}✓ Review posted{Style.RESET_ALL}")

    if json_output:
        serializable = {
            'status': result['status'],
            'passed': result['passed'],
            'event': result['event'],
            'score': result['score'],
            'findings': [f.to_dict() for f in result['findings']],
            'comments': result['comments'],
            'triage': [{'file': d.file, 'action': d.action, 'reason': d.reason} for d in result['triage']],
            'dropped_by_reason': result['dropped_by_reason'],
        }
        with open(json_output, 'w', encoding='utf-8') as fh:
            json.dump(serializable, fh, indent=2)

    if not result['passed'] and not no_fail_on_rules:
        sys.exit(1)


if __name__ == '__main__':
    main()
