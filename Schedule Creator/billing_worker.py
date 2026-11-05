"""Run separately from Flask under an always-on service supervisor."""

import logging
import time

import membership_billing
import scheduler


def main():
    logging.basicConfig(level=logging.INFO)
    scheduler.initialize_database()
    while True:
        with scheduler.app.app_context():
            membership_billing.run_once(scheduler, scheduler.billing_provider)
        time.sleep(60)


if __name__ == "__main__":
    main()
