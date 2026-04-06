"""
Utility functions for CodeSentry
"""

import os
import subprocess
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
import fnmatch


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file"""
    if not os.path.exists(config_path):
        # Try to find config in parent directories
        current_dir = Path(__file__).parent.parent
        config_path = current_dir / "config.yaml"

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def should_exclude(file_path: str, config: Dict[str, Any]) -> bool:
    """Check if file/directory should be excluded from analysis"""
    exclude_config = config.get('exclude', {})

    # Check directory exclusions
    for exclude_dir in exclude_config.get('directories', []):
        if exclude_dir in file_path:
            return True

    # Check file pattern exclusions
    filename = os.path.basename(file_path)
    for pattern in exclude_config.get('files', []):
        if fnmatch.fnmatch(filename, pattern):
            return True

    return False


def get_supported_files(directory: str, config: Dict[str, Any]) -> List[str]:
    """Get all supported files in directory recursively"""
    supported_extensions = config['static_analysis']['file_extensions']
    files = []

    for root, dirs, filenames in os.walk(directory):
        # Remove excluded directories from traversal
        dirs[:] = [d for d in dirs if not should_exclude(os.path.join(root, d), config)]

        for filename in filenames:
            file_path = os.path.join(root, filename)

            # Skip excluded files
            if should_exclude(file_path, config):
                continue

            # Check if file has supported extension
            if any(filename.endswith(ext) for ext in supported_extensions):
                files.append(file_path)

    return files


def get_file_language(file_path: str) -> str:
    """Determine programming language from file extension"""
    extension_map = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.jsx': 'JavaScript/React',
        '.ts': 'TypeScript',
        '.tsx': 'TypeScript/React',
        '.java': 'Java',
        '.cpp': 'C++',
        '.c': 'C',
        '.go': 'Go',
        '.rb': 'Ruby',
        '.php': 'PHP',
        '.rs': 'Rust',
        '.swift': 'Swift',
        '.kt': 'Kotlin',
    }

    ext = os.path.splitext(file_path)[1]
    return extension_map.get(ext, 'Unknown')


def ensure_dir(directory: str) -> None:
    """Ensure directory exists"""
    os.makedirs(directory, exist_ok=True)


def get_git_changed_files(repo_path: str, base_ref: Optional[str] = None) -> Optional[List[str]]:
    """
    Return absolute paths of files changed relative to base_ref (default: HEAD).

    Returns None if the directory is not a git repository or git is unavailable,
    so the caller can fall back to a full scan.
    """
    ref = base_ref or 'HEAD'
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', '--diff-filter=ACMRT', ref],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=30,
        )
        if result.returncode != 0:
            return None

        changed = []
        for rel_path in result.stdout.splitlines():
            rel_path = rel_path.strip()
            if rel_path:
                abs_path = os.path.join(repo_path, rel_path)
                if os.path.isfile(abs_path):
                    changed.append(abs_path)

        # Also include staged changes not yet committed
        staged = subprocess.run(
            ['git', 'diff', '--name-only', '--diff-filter=ACMRT', '--cached'],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=30,
        )
        if staged.returncode == 0:
            for rel_path in staged.stdout.splitlines():
                rel_path = rel_path.strip()
                if rel_path:
                    abs_path = os.path.join(repo_path, rel_path)
                    if os.path.isfile(abs_path) and abs_path not in changed:
                        changed.append(abs_path)

        return changed

    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
