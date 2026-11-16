"""Run every Schedule Creator test module and report results per module.

Usage (from any directory):
    python "Schedule Creator/tests/run_all_tests.py"                  # all modules
    python "Schedule Creator/tests/run_all_tests.py" test_scheduler   # selected modules
    python "Schedule Creator/tests/run_all_tests.py" -v               # verbose output
"""

import argparse
import sys
import time
import unittest
from pathlib import Path

TESTS_DIRECTORY = Path(__file__).resolve().parent
APP_DIRECTORY = TESTS_DIRECTORY.parent

# Test modules import application modules (scheduler, membership_billing, ...)
# and each other (test_scheduler, ...) by plain name.
for path in (APP_DIRECTORY, TESTS_DIRECTORY):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def available_modules():
    return sorted(path.stem for path in TESTS_DIRECTORY.glob("test_*.py"))


def main(argv=None):
    available = available_modules()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("modules", nargs="*", metavar="module",
                        help="test modules to run (default: all). Choices: " + ", ".join(available))
    parser.add_argument("-v", "--verbose", action="store_true", help="show each test name")
    parser.add_argument("-f", "--failfast", action="store_true",
                        help="stop at the first failing module")
    args = parser.parse_args(argv)

    selected = [name.removesuffix(".py") for name in args.modules] or available
    unknown = sorted(set(selected) - set(available))
    if unknown:
        parser.error("unknown test module(s): " + ", ".join(unknown))

    # Imported first so the suite is forced onto SQLite before any other
    # module can touch the deployment database configured in .env.
    import test_scheduler  # noqa: F401

    results = []
    for name in selected:
        print(f"\n=== {name} ===", flush=True)
        started = time.perf_counter()
        try:
            suite = unittest.defaultTestLoader.loadTestsFromName(name)
        except Exception as error:  # report import failures and continue with other modules
            print(f"Could not load {name}: {error!r}", flush=True)
            results.append((name, 0, 0, 1, 0, time.perf_counter() - started))
        else:
            outcome = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
            results.append((name, outcome.testsRun, len(outcome.failures), len(outcome.errors),
                            len(outcome.skipped), time.perf_counter() - started))
        if args.failfast and (results[-1][2] or results[-1][3]):
            break

    width = max(len(row[0]) for row in results)
    print("\nSummary")
    print(f"{'module':<{width}}  {'run':>5}  {'fail':>4}  {'error':>5}  {'skip':>4}  {'secs':>7}")
    for name, run, failures, errors, skipped, seconds in results:
        status = "ok" if not failures and not errors else "FAILED"
        print(f"{name:<{width}}  {run:>5}  {failures:>4}  {errors:>5}  {skipped:>4}  {seconds:>7.1f}  {status}")
    totals = [sum(row[index] for row in results) for index in range(1, 5)]
    print(f"{'TOTAL':<{width}}  {totals[0]:>5}  {totals[1]:>4}  {totals[2]:>5}  {totals[3]:>4}")
    return 0 if not totals[1] and not totals[2] else 1


if __name__ == "__main__":
    sys.exit(main())
