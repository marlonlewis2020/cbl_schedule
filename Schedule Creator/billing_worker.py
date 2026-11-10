"""Run separately from Flask under an always-on service supervisor."""

import argparse
import logging
import os
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from filelock import FileLock, Timeout

import membership_billing
import scheduler


def configure_logging(log_file):
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=3, encoding="utf-8"),
        ],
        force=True,
    )


def run_worker():
    scheduler.initialize_database()
    while True:
        with scheduler.app.app_context():
            membership_billing.run_once(scheduler, scheduler.billing_provider)
        logging.info("Billing sweep completed.")
        time.sleep(60)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--log-file", type=Path,
        default=scheduler.APP_DIRECTORY / "data" / "billing_worker.log",
    )
    arguments = parser.parse_args(argv)
    configure_logging(arguments.log_file)
    lock_path = scheduler.APP_DIRECTORY / "data" / "billing_worker.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(lock_path, timeout=0):
            logging.info("Sandbox billing worker started. pid=%s", os.getpid())
            run_worker()
    except Timeout:
        logging.warning("Another billing worker already holds this installation's lock; exiting.")
    except KeyboardInterrupt:
        logging.info("Billing worker stopped.")
    except Exception:
        logging.exception("Billing worker stopped unexpectedly; supervisor restart is required.")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
