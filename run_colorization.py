#!/usr/bin/env python3
"""Durable CBZ batch runner for the project's approved Default Model v1 pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import numpy as np
from PIL import Image, ImageFilter


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
VOLUME_RE = re.compile(r"\bv(\d{1,3})\b", re.IGNORECASE)
ROOT = Path(__file__).resolve().parent
TOOL_DIR = ROOT / "workspace" / "manga-colorization-v2"
JOBS_DIR = ROOT / "workspace" / "jobs"
OUTPUT_DIR = ROOT / "outputs"
DEVICE = "cpu"
EXPECTED_VOLUMES = 0

# Color detection thresholds
COLOR_SATURATION_THRESHOLD = 0.12  # Minimum saturation to consider a pixel colored
COLOR_FRACTION_THRESHOLD = 0.15    # Minimum fraction of colored pixels to skip colorization
SKIP_COLORED_PAGES = True          # Enable automatic colored page detection


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def safe_entry(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe archive entry: {name!r}")
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def volume_number(path: Path) -> int:
    match = VOLUME_RE.search(path.name)
    if not match:
        raise ValueError(f"cannot identify a volume number from {path.name!r}")
    return int(match.group(1))


def discover_inputs(input_dir: Path) -> list[Path]:
    candidates = []
    for path in input_dir.iterdir():
        if path.is_file() and path.suffix.lower() == ".cbz" and VOLUME_RE.search(path.name):
            candidates.append(path)
    by_volume: dict[int, Path] = {}
    for path in candidates:
        number = volume_number(path)
        if number in by_volume:
            raise ValueError(f"multiple input CBZs found for V{number:02d}")
        by_volume[number] = path
    return [by_volume[number] for number in sorted(by_volume)]


def job_dir_for(cbz: Path) -> Path:
    return JOBS_DIR / f"V{volume_number(cbz):02d}"


def initialize_job(cbz: Path) -> dict:
    job_dir = job_dir_for(cbz)
    manifest_path = job_dir / "manifest.json"
    source_hash = sha256_file(cbz)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["source_sha256"] != source_hash:
            raise RuntimeError(f"source CBZ changed for {cbz.name}; refusing to mix checkpoints")
        if manifest["source_name"] != cbz.name:
            raise RuntimeError(f"source filename changed for V{volume_number(cbz):02d}")
        return manifest

    job_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    with zipfile.ZipFile(cbz, "r") as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"input archive CRC failure at {bad!r}")
        for index, info in enumerate(archive.infolist()):
            path = safe_entry(info.filename)
            suffix = path.suffix.lower()
            is_image = not info.is_dir() and suffix in IMAGE_EXTENSIONS
            if is_image:
                try:
                    with archive.open(info) as raw, Image.open(raw) as image:
                        image.verify()
                except Exception as exc:
                    raise RuntimeError(f"invalid image entry {info.filename!r}: {exc}") from exc
            entries.append({
                "index": index,
                "name": info.filename,
                "is_dir": info.is_dir(),
                "is_image": is_image,
                "crc": info.CRC,
                "size": info.file_size,
            })
    manifest = {
        "schema": 1,
        "source_name": cbz.name,
        "source_path": str(cbz.resolve()),
        "source_sha256": source_hash,
        "volume": volume_number(cbz),
        "entries": entries,
        "image_total": sum(entry["is_image"] for entry in entries),
        "pipeline": {
            "name": "Default Model v1",
            "model": "Manga Colorization v2 stock",
            "size": 576,
            "denoiser": True,
            "denoiser_sigma": 25,
            "finishing": "original-size Lanczos restoration, mild source-detail recovery, restrained sharpening",
        },
    }
    atomic_json(manifest_path, manifest)
    write_status(job_dir, manifest, "ready")
    return manifest


def checkpoint_path(job_dir: Path, entry_name: str) -> Path:
    return job_dir / "pages" / Path(*safe_entry(entry_name).parts)


def valid_checkpoint(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except Exception:
        return False


def measure_color_content(image: Image.Image) -> dict[str, float]:
    """Measure meaningful chroma in an image (adapted from scan_manga_colors.py)."""
    rgb = image.convert("RGB")
    rgb.thumbnail((144, 144), Image.Resampling.LANCZOS)
    values = np.asarray(rgb, dtype=np.float32)
    high = values.max(axis=2)
    low = values.min(axis=2)
    saturation = (high - low) / np.maximum(high, 1.0)
    visible = high >= 35.0
    denominator = max(int(visible.sum()), 1)
    return {
        "color_fraction": float(((saturation >= COLOR_SATURATION_THRESHOLD) & visible).sum() / denominator),
        "strong_fraction": float(((saturation >= 0.25) & visible).sum() / denominator),
        "mean_saturation": float(saturation[visible].mean()) if visible.any() else 0.0,
    }


def is_already_colored(image: Image.Image) -> bool:
    """Determine if a page already has meaningful color and should be skipped."""
    if not SKIP_COLORED_PAGES:
        return False
    metrics = measure_color_content(image)
    return metrics["color_fraction"] >= COLOR_FRACTION_THRESHOLD


def create_passthrough_checkpoint(source: Image.Image, path: Path, suffix: str) -> None:
    """Save the source image as a checkpoint without colorization."""
    save_checkpoint(source, path, suffix)


def progress(manifest: dict, job_dir: Path) -> tuple[int, int]:
    images = [entry for entry in manifest["entries"] if entry["is_image"]]
    complete = sum(valid_checkpoint(checkpoint_path(job_dir, entry["name"])) for entry in images)
    return complete, len(images)


def write_status(job_dir: Path, manifest: dict, state: str, current: str | None = None) -> None:
    complete, total = progress(manifest, job_dir)
    value = {
        "volume": manifest["volume"],
        "source_name": manifest["source_name"],
        "state": state,
        "completed_pages": complete,
        "total_pages": total,
        "current_entry": current,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    atomic_json(job_dir / "status.json", value)
    write_overall_status()


def write_overall_status() -> None:
    volumes = []
    if JOBS_DIR.exists():
        for path in sorted(JOBS_DIR.glob("V*/status.json")):
            try:
                volumes.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
    atomic_json(ROOT / "progress.json", {
        "completed_volumes": sum(item["state"] == "complete" for item in volumes),
        "total_volumes": EXPECTED_VOLUMES or len(volumes),
        "volumes": volumes,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    })


def load_colorizer():
    sys.path.insert(0, str(TOOL_DIR))
    from colorizator import MangaColorizator
    # The upstream denoiser resolves its weight path relative to the process CWD.
    previous_cwd = Path.cwd()
    try:
        os.chdir(TOOL_DIR)
        return MangaColorizator(
            DEVICE,
            str(TOOL_DIR / "networks" / "generator.zip"),
            str(TOOL_DIR / "networks" / "extractor.pth"),
        )
    finally:
        os.chdir(previous_cwd)


def read_image_from_archive(cbz: Path, entry_name: str) -> Image.Image:
    with zipfile.ZipFile(cbz, "r") as archive, archive.open(entry_name) as raw:
        image = Image.open(raw)
        image.load()
        return image.convert("RGB")


def finish_image(source: Image.Image, model_rgb: np.ndarray) -> Image.Image:
    predicted = Image.fromarray(np.clip(model_rgb * 255.0, 0, 255).astype(np.uint8), "RGB")
    predicted = predicted.resize(source.size, Image.Resampling.LANCZOS)

    # Recover a small amount of high-frequency source structure without replacing
    # the model's chroma. This is intentionally conservative, matching v1 approval.
    source_gray = source.convert("L")
    low = source_gray.filter(ImageFilter.GaussianBlur(radius=1.0))
    detail = np.asarray(source_gray, dtype=np.float32) - np.asarray(low, dtype=np.float32)
    color = np.asarray(predicted, dtype=np.float32)
    color += detail[..., None] * 0.16
    finished = Image.fromarray(np.clip(color, 0, 255).astype(np.uint8), "RGB")
    return finished.filter(ImageFilter.UnsharpMask(radius=0.65, percent=35, threshold=3))


def save_checkpoint(image: Image.Image, path: Path, suffix: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=suffix, dir=path.parent)
    os.close(fd)
    try:
        params = {}
        fmt = Image.registered_extensions().get(suffix.lower())
        if suffix.lower() in {".jpg", ".jpeg"}:
            fmt, params = "JPEG", {"quality": 95, "subsampling": 0, "optimize": True}
        elif suffix.lower() == ".png":
            fmt, params = "PNG", {"compress_level": 6}
        image.save(tmp_name, format=fmt, **params)
        with Image.open(tmp_name) as check:
            check.verify()
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def colorize_batch(cbz: Path, manifest: dict, page_limit: int) -> int:
    job_dir = job_dir_for(cbz)
    pending = [entry for entry in manifest["entries"] if entry["is_image"] and
               not valid_checkpoint(checkpoint_path(job_dir, entry["name"]))]
    if not pending:
        return 0

    # Pre-scan all pending pages for color content if color detection is enabled
    pages_to_process = []
    pages_to_passthrough = []

    if SKIP_COLORED_PAGES:
        for entry in pending[:page_limit]:
            source = read_image_from_archive(cbz, entry["name"])
            if is_already_colored(source):
                pages_to_passthrough.append((entry, source))
            else:
                pages_to_process.append(entry)
    else:
        pages_to_process = pending[:page_limit]

    # Create passthrough checkpoints for already-colored pages
    for entry, source in pages_to_passthrough:
        write_status(job_dir, manifest, "running", entry["name"] + " (already colored)")
        output = checkpoint_path(job_dir, entry["name"])
        create_passthrough_checkpoint(source, output, PurePosixPath(entry["name"]).suffix)
        write_status(job_dir, manifest, "running")

    # Colorize black-and-white pages
    processed = len(pages_to_passthrough)
    if pages_to_process:
        colorizer = load_colorizer()
        for entry in pages_to_process:
            write_status(job_dir, manifest, "running", entry["name"])
            source = read_image_from_archive(cbz, entry["name"])
            # PIL can expose a read-only NumPy view for some JPEGs; the upstream
            # denoiser converts it to a tensor, so provide an explicitly writable copy.
            colorizer.set_image(np.array(source, copy=True), 576, True, 25)
            result = finish_image(source, colorizer.colorize())
            output = checkpoint_path(job_dir, entry["name"])
            save_checkpoint(result, output, PurePosixPath(entry["name"]).suffix)
            processed += 1
            write_status(job_dir, manifest, "running")

    return processed


def clone_zipinfo(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    clone = zipfile.ZipInfo(info.filename, date_time=info.date_time)
    for attr in ("compress_type", "comment", "extra", "create_system", "create_version",
                 "extract_version", "reserved", "flag_bits", "volume", "internal_attr",
                 "external_attr"):
        setattr(clone, attr, getattr(info, attr))
    return clone


def package_and_validate(cbz: Path, manifest: dict) -> Path:
    job_dir = job_dir_for(cbz)
    complete, total = progress(manifest, job_dir)
    if complete != total:
        raise RuntimeError(f"cannot package incomplete V{manifest['volume']:02d}: {complete}/{total}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    final_path = OUTPUT_DIR / cbz.name
    fd, tmp_name = tempfile.mkstemp(prefix=cbz.stem + ".", suffix=".cbz", dir=OUTPUT_DIR)
    os.close(fd)
    try:
        with zipfile.ZipFile(cbz, "r") as source, zipfile.ZipFile(tmp_name, "w", allowZip64=True) as target:
            for info in source.infolist():
                replacement = checkpoint_path(job_dir, info.filename)
                data = replacement.read_bytes() if valid_checkpoint(replacement) else source.read(info)
                target.writestr(clone_zipinfo(info), data)
        validate_output(cbz, Path(tmp_name), manifest)
        os.replace(tmp_name, final_path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
    atomic_json(job_dir / "validation.json", {
        "archive": final_path.name,
        "sha256": sha256_file(final_path),
        "entry_order_preserved": True,
        "image_names_preserved": True,
        "image_count": total,
        "zip_integrity": "passed",
        "validated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    })
    write_status(job_dir, manifest, "complete")
    return final_path


def validate_output(source_path: Path, output_path: Path, manifest: dict) -> None:
    with zipfile.ZipFile(source_path, "r") as source, zipfile.ZipFile(output_path, "r") as output:
        source_names = [info.filename for info in source.infolist()]
        output_names = [info.filename for info in output.infolist()]
        if output_names != source_names:
            raise RuntimeError("output archive entry names/order do not match input")
        bad = output.testzip()
        if bad:
            raise RuntimeError(f"output archive CRC failure at {bad!r}")
        for entry in manifest["entries"]:
            if not entry["is_image"]:
                continue
            with output.open(entry["name"]) as raw, Image.open(raw) as image:
                image.verify()


def run(args: argparse.Namespace) -> int:
    global JOBS_DIR, OUTPUT_DIR, DEVICE, EXPECTED_VOLUMES, SKIP_COLORED_PAGES, COLOR_FRACTION_THRESHOLD
    JOBS_DIR = args.jobs_dir.resolve()
    OUTPUT_DIR = args.output_dir.resolve()
    DEVICE = args.device
    SKIP_COLORED_PAGES = args.skip_colored
    COLOR_FRACTION_THRESHOLD = args.color_threshold
    inputs = discover_inputs(args.input_dir)
    if not inputs:
        print(f"No volume-numbered CBZ inputs found in {args.input_dir}", file=sys.stderr)
        return 2
    EXPECTED_VOLUMES = len(inputs)
    remaining = args.pages
    for cbz in inputs:
        manifest = initialize_job(cbz)
        complete, total = progress(manifest, job_dir_for(cbz))
        if complete == total:
            if not (OUTPUT_DIR / cbz.name).is_file():
                package_and_validate(cbz, manifest)
            else:
                write_status(job_dir_for(cbz), manifest, "complete")
            continue
        if remaining <= 0:
            break
        used = colorize_batch(cbz, manifest, remaining)
        remaining -= used
        complete, total = progress(manifest, job_dir_for(cbz))
        if complete == total:
            package_and_validate(cbz, manifest)
        else:
            write_status(job_dir_for(cbz), manifest, "checkpointed")
        if remaining <= 0:
            break
    write_overall_status()
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=ROOT / "inputs")
    parser.add_argument("--jobs-dir", type=Path, default=ROOT / "workspace" / "jobs")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--pages", type=int, default=8, help="maximum pages in this explicit batch")
    parser.add_argument("--skip-colored", action="store_true", default=True,
                        help="automatically detect and skip already-colored pages (default: enabled)")
    parser.add_argument("--no-skip-colored", dest="skip_colored", action="store_false",
                        help="disable automatic colored page detection")
    parser.add_argument("--color-threshold", type=float, default=0.15,
                        help="minimum color fraction to consider a page already colored (default: 0.15)")
    args = parser.parse_args()
    if args.pages < 1:
        parser.error("--pages must be positive")
    if not 0.0 <= args.color_threshold <= 1.0:
        parser.error("--color-threshold must be between 0.0 and 1.0")
    return args


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
