"""Download and verify the pinned E5 encoder during image build."""

import hashlib
import json
from pathlib import Path

from huggingface_hub import snapshot_download


def main():

    manifest = json.loads(
        Path(__file__).with_name(
            "e5_model_manifest.json"
        ).read_text(encoding="utf-8")
    )

    snapshot = Path(
        snapshot_download(
            repo_id=manifest["model_name"],
            revision=manifest["revision"],
            allow_patterns=list(manifest["files"]),
            token=False,
        )
    )

    if snapshot.name != manifest["revision"]:
        raise RuntimeError("Unexpected model revision.")

    for filename, expected in manifest["files"].items():

        path = snapshot / filename

        if not path.is_file():
            raise RuntimeError(
                f"Missing model file: {filename}"
            )

        if path.stat().st_size != expected["bytes"]:
            raise RuntimeError(
                f"Invalid model file size: {filename}"
            )

        with path.open("rb") as handle:

            digest = hashlib.file_digest(
                handle,
                "sha256",
            ).hexdigest()

        if digest != expected["sha256"]:
            raise RuntimeError(
                f"Model integrity failure: {filename}"
            )

        print("Verified:", filename, flush=True)

    print("MODEL PROVISIONING PASSED", flush=True)
    print("Revision:", manifest["revision"], flush=True)


if __name__ == "__main__":
    main()
