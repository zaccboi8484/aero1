"""Strict suppression loading and crash-resistant JSON publication (single writer)."""
import json
import os
from pathlib import Path
import tempfile


def load_suppression(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set()  # A fresh install has no recorded opt-outs.
    if not isinstance(data, dict) or not isinstance(data.get("pins"), list):
        raise ValueError("Invalid suppression file: expected a pins list; refusing to proceed")
    if any(not isinstance(p, str) or not p.strip() for p in data["pins"]):
        raise ValueError("Invalid suppression PIN; refusing to proceed")
    return set(data["pins"])


def atomic_json(path, data):
    path = Path(path)
    payload = json.dumps(data, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="." + path.name, delete=False) as stream:
            name = stream.name
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
