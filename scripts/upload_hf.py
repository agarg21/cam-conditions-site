#!/usr/bin/env python3
"""Upload this run's out/ folder to the private Hugging Face dataset under raw/.

Needs HF_TOKEN (fine-grained, write access to the dataset only).
"""
import os
import sys

from huggingface_hub import HfApi

REPO = os.environ.get("HF_DATASET", "agarg20/conditionsnow-cams")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("HF_TOKEN not set; skipping upload")
        return 0
    out = os.path.join(ROOT, "out")
    if not os.path.isdir(out):
        print("nothing to upload")
        return 0
    api = HfApi(token=token)
    info = api.upload_folder(
        repo_id=REPO,
        repo_type="dataset",
        folder_path=out,
        path_in_repo="raw",
        commit_message=f"collect {os.environ.get('GITHUB_RUN_ID', 'local')}",
    )
    print("uploaded:", info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
