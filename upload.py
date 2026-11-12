"""Качва модела и кода в HuggingFace Hub.

Преди това влез веднъж:  .venv/bin/hf auth login
Пускане:                 .venv/bin/python upload.py [име-на-репо] [--private]
"""
import sys

from huggingface_hub import HfApi

CARD = """---
language: bg
library_name: pytorch
pipeline_tag: text-generation
thumbnail: https://huggingface.co/Kirsko/krisko-purvi/resolve/main/avatar.png
tags:
  - from-scratch
  - tiny
  - chatbot
---

"""

api = HfApi()
args = [a for a in sys.argv[1:] if not a.startswith("--")]
name = args[0] if args else "krisko-purvi"
repo_id = name if "/" in name else f"{api.whoami()['name']}/{name}"
api.create_repo(repo_id, exist_ok=True, private="--private" in sys.argv)
api.upload_folder(folder_path="model", path_in_repo="model", repo_id=repo_id)
for file in ("model.py", "chat.py", "app.py", "train.py", "avatar.png", "requirements.txt"):
    api.upload_file(path_or_fileobj=file, path_in_repo=file, repo_id=repo_id)
with open("README.md", encoding="utf-8") as f:   # същото описание + данни за HuggingFace отгоре
    api.upload_file(path_or_fileobj=(CARD + f.read()).encode("utf-8"), path_in_repo="README.md", repo_id=repo_id)
print(f"Качено: https://huggingface.co/{repo_id}")
