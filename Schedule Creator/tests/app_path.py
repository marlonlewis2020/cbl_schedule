"""Make the Schedule Creator application modules importable from the tests folder.

Imported first by each test module so it also works when run directly, e.g.
``python tests/test_scheduler.py``.
"""

import sys
from pathlib import Path

APP_DIRECTORY = Path(__file__).resolve().parent.parent
TESTS_DIRECTORY = Path(__file__).resolve().parent

for path in (TESTS_DIRECTORY, APP_DIRECTORY):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
