"""Run under a supervisor with the same environment/database as Flask."""
import logging
import time

import attendance_reports
import scheduler


def main():
    logging.basicConfig(level=logging.INFO)
    scheduler.initialize_database()
    while True:
        with scheduler.app.app_context():
            attendance_reports.run_once(scheduler)
        time.sleep(30)


if __name__ == "__main__":
    main()
