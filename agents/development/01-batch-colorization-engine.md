# ⚙️ Batch Colorization Engine

## 1. Overview & Purpose

The Batch Colorization Engine (`run_colorization.py`) is the primary driver for processing CBZ manga archives. It orchestrates volume discovery, page budget allocation, model initialization, color pre-scanning, image finishing, and overall progress broadcasting.

---

## 2. Command-Line Arguments & CLI Options

The runner exposes a rich set of command-line arguments:

```bash
python run_colorization.py [OPTIONS]
```

### Argument Reference

| Flag | Type | Default | Description |
|---|---|---|---|
| `--input-dir` | `Path` | `ROOT / "inputs"` | Directory containing source CBZ archives. |
| `--jobs-dir` | `Path` | `ROOT / "workspace" / "jobs"` | Directory storing per-volume manifests, status, and checkpoints. |
| `--output-dir` | `Path` | `ROOT / "outputs"` | Directory where finished, validated CBZs are placed. |
| `--device` | `str` (`cpu`, `cuda`) | `"cpu"` | Compute device for PyTorch inference. Strongly recommend `cuda` for production batches. |
| `--pages` | `int` | `8` | Maximum number of pages to process in the current execution run (budgeting). |
| `--skip-colored` | `bool` | `True` | Automatically pre-scans and passes through already-colored pages. |
| `--no-skip-colored` | `flag` | N/A | Disables color detection; forces all pages through neural colorization. |
| `--color-threshold` | `float` | `0.15` | Minimum fraction of colored pixels required to classify a page as already colored. |

---

## 3. Core Engine Architecture

### Volume Discovery (`discover_inputs`)
- Scans `input_dir` for files ending in `.cbz`.
- Extracts volume number using regex: `r"\bv(\d{1,3})\b"` (case-insensitive).
- Enforces uniqueness: Rejects duplicate volume numbers (e.g., having two files representing Volume 1).
- Returns a sorted list of inputs ordered by volume number.

```python
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
```

### Multi-Volume Sequential Loop (`run`)
The engine iterates through the discovered volumes sequentially, maintaining a global `remaining` page budget:

```python
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
```

---

## 4. Batch Page Processing (`colorize_batch`)

Within each volume:
1. **Identifies Pending Pages**: Filters `manifest["entries"]` for un-checkpointed image entries.
2. **Color Pre-Scan**: Evaluates up to `page_limit` pending pages. If `--skip-colored` is active, partitions pages into `pages_to_passthrough` and `pages_to_process`.
3. **Passthrough Checkpoint Creation**: For already-colored pages, writes the original image directly to disk as a verified checkpoint without touching PyTorch.
4. **Neural Colorization**: For black-and-white pages:
   - Lazily loads `colorizator` on first B&W page.
   - Converts source to a writable NumPy array (`np.array(source, copy=True)`).
   - Ingests image via `colorizer.set_image(..., 576, True, 25)`.
   - Generates colorized array with `colorizer.colorize()`.
   - Runs post-inference finishing (`finish_image`).
   - Atomically saves and verifies the checkpoint.
   - Updates `status.json`.

---

## 5. Global Progress Tracking (`progress.json`)

The engine periodically updates `progress.json` in the root workspace to provide real-time batch visibility:

```json
{
  "completed_volumes": 1,
  "total_volumes": 3,
  "volumes": [
    {
      "volume": 1,
      "source_name": "Manga v01.cbz",
      "state": "complete",
      "completed_pages": 192,
      "total_pages": 192,
      "current_entry": null,
      "updated_at": "2026-09-10T20:50:12+00:00"
    },
    {
      "volume": 2,
      "source_name": "Manga v02.cbz",
      "state": "running",
      "completed_pages": 45,
      "total_pages": 204,
      "current_entry": "Ch. 12/page_004.png",
      "updated_at": "2026-09-10T20:55:34+00:00"
    }
  ],
  "updated_at": "2026-09-10T20:55:34+00:00"
}
```

---

## 6. Error Handling & Invariants

- **Archive CRC Validation**: Prior to starting any job, the archive's ZIP CRC is validated via `archive.testzip()`.
- **Image Entry Verification**: Every image entry is opened and verified with PIL during manifest initialization.
- **Atomic State Writes**: All `status.json` and `progress.json` writes use `atomic_json` (`tempfile` + `fsync` + `os.replace`).
- **Clean Interruption**: If the process is terminated (SIGINT / Ctrl+C), all already-saved page checkpoints remain valid and clean on disk.
