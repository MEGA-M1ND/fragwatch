"""Retired. Superseded by `sections.py --check`.

This module verified a handful of fixed strings such as "Nine developmental campaigns" and could not
notice a changed number elsewhere in a document. Every numerical claim is now generated from the
canonical summary and verified by regenerating it in memory.
"""

import sys

print(__doc__, file=sys.stderr)
print("Run instead:  python src/fragwatch/sections.py --check", file=sys.stderr)
raise SystemExit(2)
