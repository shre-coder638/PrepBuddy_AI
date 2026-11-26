"""Start the restricted PrepBuddy gateway on localhost."""

import argparse
import getpass
import os

from deploy.hybrid_gateway import create_app


def read_setting(name):
    return os.getenv(name) or getpass.getpass(
        name + ": "
    )


def main():
    parser = argparse.ArgumentParser(
        description="PrepBuddy restricted hybrid gateway"
    )

    parser.add_argument(
        "--enable-send",
        action="store_true",
        help="Explicitly enable allowlisted WhatsApp delivery.",
    )

    args = parser.parse_args()

    application = create_app(
        ann_token=read_setting("ANN_SERVICE_TOKEN"),
        proxy_token=read_setting("OPENWA_PROXY_TOKEN"),
        openwa_key=read_setting("OPENWA_API_KEY"),
        session_id=read_setting("OPENWA_SESSION_ID"),
        allowed_phone=read_setting("DEMO_ALLOWED_PHONE"),
        allow_send=args.enable_send,
    )

    from waitress import serve

    print("Gateway: http://127.0.0.1:8012")
    print("WhatsApp delivery:",
          "ENABLED" if args.enable_send else "DISABLED")
    print("Recipient allowlist: ACTIVE")

    serve(
        application,
        host="127.0.0.1",
        port=8012,
        threads=4,
        channel_timeout=30,
        max_request_body_size=131072,
        max_request_header_size=16384,
        expose_tracebacks=False,
    )


if __name__ == "__main__":
    main()
