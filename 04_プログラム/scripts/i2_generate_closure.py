"""STEP 3: 閉鎖辞書を JSON / CSV に展開する。"""

from __future__ import annotations

import csv
import json
import pickle
from pathlib import Path

import config


def ensure_output_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def load_closure_dict(path: str) -> dict[str, list[str]]:
    with open(path, "rb") as f:
        return pickle.load(f)


def save_closure_json(closure_dict: dict[str, list[str]], path: str) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(closure_dict, f, ensure_ascii=False, indent=2)
    except PermissionError:
        if Path(path).exists():
            with open(path, encoding="utf-8") as f:
                json.load(f)
            print(f"[WARN] 既存JSONを上書きできないため保持: {path}")
            return False
        raise
    return True


def save_closure_csv(closure_dict: dict[str, list[str]], path: str) -> bool:
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "edge_id"])
            for ts, edge_ids in closure_dict.items():
                for edge_id in edge_ids:
                    writer.writerow([ts, edge_id])
    except PermissionError:
        if Path(path).exists():
            with open(path, newline="", encoding="utf-8") as f:
                next(csv.reader(f), None)
            print(f"[WARN] 既存CSVを上書きできないため保持: {path}")
            return False
        raise
    return True


def main() -> None:
    ensure_output_dir(config.OUT_CLOSURE_DIR)
    closure = load_closure_dict(config.CLOSURE_PKL_PATH)
    for ts, edge_ids in closure.items():
        print(f"{ts}: {len(edge_ids)} edges")
    if save_closure_json(closure, config.CLOSURE_JSON_PATH):
        print(f"[INFO] saved: {config.CLOSURE_JSON_PATH}")
    if save_closure_csv(closure, config.CLOSURE_CSV_PATH):
        print(f"[INFO] saved: {config.CLOSURE_CSV_PATH}")


if __name__ == "__main__":
    main()
