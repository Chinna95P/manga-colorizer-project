#!/usr/bin/env python3
"""Measure meaningful chroma in every page of a directory of CBZ archives."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import zipfile
from pathlib import Path, PurePosixPath

import numpy as np
from PIL import Image


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def measure(image: Image.Image) -> dict[str, float | str]:
    original_mode = image.mode
    rgb = image.convert("RGB")
    rgb.thumbnail((144, 144), Image.Resampling.LANCZOS)
    values = np.asarray(rgb, dtype=np.float32)
    high = values.max(axis=2)
    low = values.min(axis=2)
    saturation = (high - low) / np.maximum(high, 1.0)
    visible = high >= 35.0
    denominator = max(int(visible.sum()), 1)
    return {
        "mode": original_mode,
        "color_fraction": round(float(((saturation >= 0.12) & visible).sum() / denominator), 6),
        "strong_fraction": round(float(((saturation >= 0.25) & visible).sum() / denominator), 6),
        "mean_saturation": round(float(saturation[visible].mean()) if visible.any() else 0.0, 6),
    }


def scan_archive(path: Path) -> dict:
    pages = []
    with zipfile.ZipFile(path) as archive:
        if bad := archive.testzip():
            raise RuntimeError(f"CRC failure in {path.name}: {bad}")
        for info in archive.infolist():
            if info.is_dir() or PurePosixPath(info.filename).suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            with archive.open(info) as raw, Image.open(raw) as image:
                metrics = measure(image)
            pages.append({"name": info.filename, **metrics})
    return {"archive": path.name, "pages": pages}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=min(6, os.cpu_count() or 1))
    args = parser.parse_args()
    archives = sorted(args.source.glob("*.cbz"))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(scan_archive, archives))
    payload = {
        "schema": 1,
        "source": str(args.source.resolve()),
        "archives": results,
        "total_pages": sum(len(item["pages"]) for item in results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Scanned {len(results)} archives and {payload['total_pages']} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
