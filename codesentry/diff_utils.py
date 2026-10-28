"""
Diff Utilities - Parse unified diffs into line maps for PR review

GitHub only accepts inline review comments on lines that appear in the
pull request diff. `parse_patch` turns the `patch` field GitHub returns for
each changed file into the sets of new-file line numbers that were added or
are visible as context, so findings can be scoped to what the PR changed.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Set

_HUNK_HEADER = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


@dataclass
class PatchInfo:
    added_lines: Set[int] = field(default_factory=set)
    context_lines: Set[int] = field(default_factory=set)
    added_content: Dict[int, str] = field(default_factory=dict)
    removed_content: List[str] = field(default_factory=list)

    @property
    def commentable_lines(self) -> Set[int]:
        """New-file lines GitHub will accept an inline comment on"""
        return self.added_lines | self.context_lines

    @property
    def changed_text(self) -> List[str]:
        return [self.added_content[n] for n in sorted(self.added_content)]


def parse_patch(patch: str) -> PatchInfo:
    """Parse a unified diff (one file) into added/context line maps"""
    info = PatchInfo()
    if not patch:
        return info

    new_line = 0
    in_hunk = False
    for raw in patch.splitlines():
        header = _HUNK_HEADER.match(raw)
        if header:
            new_line = int(header.group(3))
            in_hunk = True
            continue
        if not in_hunk or raw.startswith('\\'):
            continue  # file headers, or "\ No newline at end of file"
        if raw.startswith('+'):
            info.added_lines.add(new_line)
            info.added_content[new_line] = raw[1:]
            new_line += 1
        elif raw.startswith('-'):
            info.removed_content.append(raw[1:])
        else:
            info.context_lines.add(new_line)
            new_line += 1
    return info


def nearest_added_line(line: int, info: PatchInfo, max_distance: int = 3) -> int:
    """Snap a line to the closest added line within `max_distance`, else 0"""
    if line in info.added_lines:
        return line
    candidates = [n for n in info.added_lines if abs(n - line) <= max_distance]
    if not candidates:
        return 0
    return min(candidates, key=lambda n: (abs(n - line), n))
