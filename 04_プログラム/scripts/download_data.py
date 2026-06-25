from __future__ import annotations

import argparse
import csv
import shutil
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PROJECT_DIR.parent
MANIFEST_PATH = PROJECT_DIR / "data" / "manifest.csv"


@dataclass(frozen=True)
class Dataset:
    dataset_id: str
    name: str
    source_url: str
    local_path: Path
    download_method: str
    archive_name: str


def load_manifest(path: Path) -> list[Dataset]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        return [
            Dataset(
                dataset_id=row["dataset_id"],
                name=row["name"],
                source_url=row["source_url"],
                local_path=PROJECT_DIR / row["local_path"],
                download_method=row["download_method"],
                archive_name=row["archive_name"],
            )
            for row in rows
        ]


def download_file(url: str, destination: Path, overwrite: bool) -> None:
    if destination.exists() and not overwrite:
        print(f"skip: {destination} already exists")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    print(f"download: {url}")
    with urllib.request.urlopen(url) as response, tmp_path.open("wb") as f:
        shutil.copyfileobj(response, f)
    tmp_path.replace(destination)


def extract_zip(archive_path: Path, destination: Path, overwrite: bool) -> None:
    if destination.exists() and any(destination.iterdir()) and not overwrite:
        print(f"skip: {destination} already extracted")
        return

    destination.mkdir(parents=True, exist_ok=True)
    print(f"extract: {archive_path} -> {destination}")
    with zipfile.ZipFile(archive_path) as zf:
        zf.extractall(destination)


def sync_dataset(dataset: Dataset, overwrite: bool) -> None:
    if dataset.download_method != "direct_zip":
        print(f"manual: {dataset.dataset_id} ({dataset.name})")
        print(f"  source: {dataset.source_url}")
        print(f"  place under: {dataset.local_path}")
        return

    if not dataset.archive_name:
        raise ValueError(f"{dataset.dataset_id}: archive_name is required for direct_zip")

    archive_path = dataset.local_path.parent / dataset.archive_name
    download_file(dataset.source_url, archive_path, overwrite)
    extract_zip(archive_path, dataset.local_path, overwrite)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download reproducible input datasets.")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--dataset", action="append", help="Dataset ID to download. Repeatable.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing archives/extracted files.")
    args = parser.parse_args()

    datasets = load_manifest(args.manifest)
    if args.dataset:
        selected = set(args.dataset)
        datasets = [dataset for dataset in datasets if dataset.dataset_id in selected]
        missing = selected - {dataset.dataset_id for dataset in datasets}
        if missing:
            print(f"unknown dataset id(s): {', '.join(sorted(missing))}", file=sys.stderr)
            return 2

    for dataset in datasets:
        sync_dataset(dataset, overwrite=args.overwrite)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
