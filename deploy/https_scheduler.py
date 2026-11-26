"""Standalone HTTPS scheduler for PrepBuddy hybrid staging."""

import argparse
import getpass
import json
import os
import re
import time

import requests


SCHEDULER_URL = (
    "https://prepbuddy-ann-staging.onrender.com"
    "/internal/scheduler/v1/tick/"
)

INTERVAL_SECONDS = 60
MAX_RESPONSE_BYTES = 4096


class SchedulerError(RuntimeError):
    pass


class SchedulerConfigurationError(SchedulerError):
    pass


def run_tick(session, token):
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
        raise SchedulerConfigurationError(
            "Invalid scheduler token format."
        )

    with session.post(
        SCHEDULER_URL,
        data=b"{}",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=(5, 65),
        allow_redirects=False,
        stream=True,
        verify=True,
    ) as response:

        if response.status_code in (401, 403, 404, 405):
            raise SchedulerConfigurationError(
                f"Scheduler rejected request: HTTP {response.status_code}"
            )

        if 300 <= response.status_code < 400:
            raise SchedulerConfigurationError(
                "Unexpected redirect. Scheduler stopped."
            )

        if response.status_code != 200:
            raise SchedulerError(
                f"Scheduler unavailable: HTTP {response.status_code}"
            )

        body = bytearray()

        for chunk in response.iter_content(chunk_size=1024):
            body.extend(chunk)

            if len(body) > MAX_RESPONSE_BYTES:
                raise SchedulerError(
                    "Scheduler response too large."
                )

        try:
            result = json.loads(body)
        except (ValueError, UnicodeError):
            raise SchedulerError(
                "Invalid scheduler response."
            ) from None

        if (
            not isinstance(result, dict)
            or set(result) != {"status", "mode"}
            or result["status"] not in ("ok", "busy")
            or result["mode"] not in (
                "heartbeat-only",
                "reconciliation",
                "reconciliation-and-delivery",
            )
        ):
            raise SchedulerError(
                "Unexpected scheduler response."
            )

        return result


def main():
    parser = argparse.ArgumentParser(
        description="PrepBuddy HTTPS scheduler"
    )

    mode = parser.add_mutually_exclusive_group(required=True)

    mode.add_argument("--once", action="store_true")
    mode.add_argument("--loop", action="store_true")

    args = parser.parse_args()

    token = os.getenv("HTTPS_SCHEDULER_TOKEN") or getpass.getpass(
        "Scheduler token: "
    )

    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
        print("Invalid scheduler token format.")
        return 1

    try:
        with requests.Session() as session:
            session.trust_env = False

            while True:
                try:
                    result = run_tick(session, token)

                    print(
                        time.strftime("%Y-%m-%d %H:%M:%S"),
                        "|", result["status"].upper(),
                        "|", result["mode"],
                        flush=True,
                    )

                    if args.once:
                        return 0

                except SchedulerConfigurationError as exc:
                    print(str(exc), flush=True)
                    return 1

                except SchedulerError as exc:
                    print(str(exc), flush=True)

                    if args.once:
                        return 1

                except requests.RequestException as exc:
                    print(
                        "Network failure:",
                        type(exc).__name__,
                        flush=True,
                    )

                    if args.once:
                        return 1

                time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nScheduler stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
