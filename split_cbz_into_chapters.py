#!/usr/bin/env python3
"""Split colorized volume CBZs into validated chapter CBZs."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import zipfile
from collections import OrderedDict
from pathlib import Path, PurePosixPath


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
CHAPTER_RE = re.compile(r"\bCh\.\s*\d", re.IGNORECASE)
VOLUME_RE = re.compile(r"\bv(\d{1,3})\b", re.IGNORECASE)


def chapter_component(name: str) -> tuple[int, str]:
    parts = PurePosixPath(name).parts
    for index, part in enumerate(parts[:-1]):
        if CHAPTER_RE.search(part):
            return index, part
    raise ValueError(f"image is not inside a recognizable chapter folder: {name!r}")


def clone_info(source: zipfile.ZipInfo, name: str) -> zipfile.ZipInfo:
    clone = zipfile.ZipInfo(name, source.date_time)
    for attr in (
        "compress_type", "comment", "extra", "create_system", "create_version",
        "extract_version", "reserved", "flag_bits", "volume", "internal_attr",
        "external_attr",
    ):
        setattr(clone, attr, getattr(source, attr))
    return clone


def volume_number(path: Path) -> int:
    match = VOLUME_RE.search(path.name)
    if not match:
        raise ValueError(f"no volume number in {path.name!r}")
    return int(match.group(1))


def split_volume(source_path: Path, staging: Path) -> list[dict]:
    chapters: OrderedDict[str, list[tuple[zipfile.ZipInfo, str]]] = OrderedDict()
    with zipfile.ZipFile(source_path) as source:
        if bad := source.testzip():
            raise RuntimeError(f"CRC failure in {source_path.name}: {bad}")
        for info in source.infolist():
            if info.is_dir() or PurePosixPath(info.filename).suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            component_index, chapter = chapter_component(info.filename)
            parts = PurePosixPath(info.filename).parts
            member_name = PurePosixPath(*parts[component_index + 1:]).as_posix()
            chapters.setdefault(chapter, []).append((info, member_name))

        results = []
        for chapter, members in chapters.items():
            final_path = staging / f"{chapter}.cbz"
            if final_path.exists():
                raise RuntimeError(f"duplicate chapter output name: {final_path.name}")
            fd, tmp_name = tempfile.mkstemp(prefix=final_path.stem + ".", suffix=".cbz", dir=staging)
            os.close(fd)
            tmp_path = Path(tmp_name)
            try:
                with zipfile.ZipFile(tmp_path, "w", allowZip64=True) as target:
                    for info, member_name in members:
                        target.writestr(clone_info(info, member_name), source.read(info))
                with zipfile.ZipFile(tmp_path) as check:
                    if bad := check.testzip():
                        raise RuntimeError(f"CRC failure in generated {final_path.name}: {bad}")
                    actual = [item.filename for item in check.infolist()]
                    expected = [member_name for _, member_name in members]
                    if actual != expected:
                        raise RuntimeError(f"page order mismatch in {final_path.name}")
                os.replace(tmp_path, final_path)
            finally:
                tmp_path.unlink(missing_ok=True)
            results.append({
                "volume": volume_number(source_path),
                "chapter": chapter,
                "archive": final_path.name,
                "pages": len(members),
            })
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    volumes = sorted(args.input_dir.glob("*.cbz"), key=volume_number)
    if not volumes:
        parser.error("no volume CBZ files found")
    if args.output_dir.exists():
        parser.error(f"output already exists: {args.output_dir}")

    staging = args.output_dir.with_name(args.output_dir.name + ".in-progress")
    if staging.exists():
        parser.error(f"staging directory already exists: {staging}")
    staging.mkdir(parents=True)
    try:
        chapters = []
        for volume in volumes:
            chapters.extend(split_volume(volume, staging))
        manifest = {
            "source_volumes": len(volumes),
            "chapter_archives": len(chapters),
            "total_pages": sum(item["pages"] for item in chapters),
            "page_order": "preserved from source volumes",
            "chapters": chapters,
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        os.replace(staging, args.output_dir)
    except BaseException:
        # Keep staging on failure for inspection; never expose it as final output.
        raise
    print(f"Created {len(chapters)} chapter CBZs with {manifest['total_pages']} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
