"""Where snapshots and recordings live: $VIBESIM_DATA_DIR, default ~/.local/share/vibesim."""

import json
import os
from pathlib import Path
from typing import Any


def data_dir() -> Path:
    return Path(os.environ.get("VIBESIM_DATA_DIR", Path.home() / ".local" / "share" / "vibesim"))


def snapshot_path(simulation_id: str) -> Path:
    return data_dir() / "snapshots" / f"{simulation_id}.json"


def recording_path(recording_id: str) -> Path:
    return data_dir() / "recordings" / f"{recording_id}.jsonl"


def save_snapshot(simulation_id: str, snapshot: dict[str, Any]) -> None:
    path = snapshot_path(simulation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot))
    tmp.replace(path)  # atomic: a crash mid-write never leaves a half snapshot


def load_snapshots() -> list[dict[str, Any]]:
    folder = data_dir() / "snapshots"
    return [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))] if folder.exists() else []


def delete_snapshot(simulation_id: str) -> None:
    snapshot_path(simulation_id).unlink(missing_ok=True)


def list_recordings() -> list[str]:
    folder = data_dir() / "recordings"
    return sorted(p.stem for p in folder.glob("*.jsonl")) if folder.exists() else []
