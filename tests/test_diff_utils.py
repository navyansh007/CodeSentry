import unittest

from codesentry.diff_utils import nearest_added_line, numbered_windows, parse_patch

PATCH = '''@@ -1,4 +1,5 @@
 import os
-import sys
+import json
+import re
 
 def main():
@@ -20,3 +21,4 @@ def helper():
     x = 1
+    y = 2
     return x
\\ No newline at end of file'''


class ParsePatchTests(unittest.TestCase):
    def test_line_maps(self):
        info = parse_patch(PATCH)
        self.assertEqual(info.added_lines, {2, 3, 22})
        self.assertEqual(info.context_lines, {1, 4, 5, 21, 23})
        self.assertEqual(info.added_content[3], 'import re')
        self.assertEqual(info.removed_content, ['import sys'])
        self.assertEqual(info.changed_text, ['import json', 'import re', '    y = 2'])
        self.assertEqual(info.commentable_lines, {1, 2, 3, 4, 5, 21, 22, 23})

    def test_added_line_that_looks_like_a_header(self):
        info = parse_patch('@@ -1 +1,2 @@\n x\n+++counter\n')
        self.assertEqual(info.added_content, {2: '++counter'})

    def test_empty_patch(self):
        self.assertEqual(parse_patch('').added_lines, set())
        self.assertEqual(parse_patch(None).added_lines, set())

    def test_nearest_added_line(self):
        info = parse_patch(PATCH)
        self.assertEqual(nearest_added_line(22, info), 22)
        self.assertEqual(nearest_added_line(24, info), 22)
        self.assertEqual(nearest_added_line(12, info), 0)


class NumberedWindowsTests(unittest.TestCase):
    def test_merges_and_marks(self):
        lines = [f'l{i}' for i in range(1, 101)]
        out = numbered_windows(lines, {10, 14, 80}, context=2)
        self.assertIn('+   10 | l10', out)
        self.assertIn('    12 | l12', out)
        self.assertNotIn('l20', out)
        self.assertEqual(out.count('...'), 1)  # 8-16 merged, 78-82 separate
        self.assertEqual(numbered_windows(lines, set()), '')


if __name__ == '__main__':
    unittest.main()
