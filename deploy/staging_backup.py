"""Temporary encrypted backup service for synthetic staging data."""

import hmac
import json
import os
import re
import subprocess
import tempfile

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote

from cryptography.fernet import Fernet


TOKEN = os.environ["BACKUP_ACCESS_TOKEN"]
CIPHER = Fernet(os.environ["BACKUP_ENCRYPTION_KEY"].encode())

if not re.fullmatch(r"[A-Za-z0-9_-]{64}", TOKEN):
    raise RuntimeError("Invalid backup authentication configuration.")

parsed = urlsplit(os.environ["BACKUP_DATABASE_URL"])

database = unquote(parsed.path.lstrip("/"))

if (
    parsed.scheme not in ("postgres", "postgresql")
    or not re.fullmatch(r"dpg-[a-z0-9-]+", parsed.hostname or "")
    or database != "prepbuddy_ann_staging"
    or not parsed.username
    or not parsed.password
    or parsed.port not in (None, 5432)
    or parsed.query
    or parsed.fragment
):
    raise RuntimeError("Invalid internal staging database configuration.")

MAX_BACKUP_BYTES = 16 * 1024 * 1024


def create_backup():
    env = {
        "PATH": os.environ["PATH"],
        "PGHOST": parsed.hostname,
        "PGPORT": str(parsed.port or 5432),
        "PGDATABASE": database,
        "PGUSER": unquote(parsed.username),
        "PGPASSWORD": unquote(parsed.password),
        "PGSSLMODE": "require",
        "PGCONNECT_TIMEOUT": "10",
        "PGOPTIONS": "-c default_transaction_read_only=on",
    }

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "backup.dump"

        subprocess.run(
            [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                "--no-password",
                "--file", str(path),
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=90,
            check=True,
        )

        if not 0 < path.stat().st_size <= MAX_BACKUP_BYTES:
            raise RuntimeError("Unexpected backup size.")

        subprocess.run(
            ["pg_restore", "--list", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=True,
        )

        return CIPHER.encrypt(path.read_bytes())


class Handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def respond(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def error(self, status):
        self.respond(
            status,
            json.dumps({"status": "rejected"}).encode(),
            "application/json",
        )

    def do_GET(self):
        if self.path == "/healthz/":
            self.respond(
                200, b'{"status":"ok"}', "application/json"
            )
        else:
            self.error(404)

    def do_POST(self):
        if self.path != "/internal/backup/v1/download/":
            self.error(404)
            return

        supplied = self.headers.get("Authorization", "")

        if not hmac.compare_digest(
            supplied.encode(),
            ("Bearer " + TOKEN).encode(),
        ):
            self.error(401)
            return

        if (
            self.headers.get("Content-Length") != "0"
            or self.headers.get("Transfer-Encoding")
        ):
            self.error(400)
            return

        try:
            encrypted = create_backup()
        except Exception:
            self.error(503)
            return

        self.respond(
            200, encrypted, "application/octet-stream"
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))

    server = HTTPServer(("0.0.0.0", port), Handler)
    print("Encrypted staging backup service ready.", flush=True)
    server.serve_forever()
