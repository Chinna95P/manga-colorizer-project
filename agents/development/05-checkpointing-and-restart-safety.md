# 💾 Checkpointing & Restart Safety

## 1. Overview & Core Philosophy

Large manga volumes contain hundreds of high-resolution pages, and processing a multi-volume library can take substantial time. A critical architectural requirement is **100% restart safety**:
- If power is cut, GPU memory overflows, or the user interrupts the script (Ctrl+C), no completed work is lost.
- Re-running the batch runner immediately picks up at the exact next un-processed page.
- Corrupted or partial files are never treated as valid checkpoints.
- Input changes prevent accidental pollution of existing checkpoints.

---

## 2. Job Workspace Structure (`workspace/jobs/`)

Each volume is isolated in its own dedicated job directory named `V{number:02d}`:

```
workspace/jobs/V01/
├── manifest.json       # Source archive fingerprint, entries, pipeline config
├── status.json         # Real-time state, completed/total count, current page
├── validation.json     # Final output integrity certification
└── pages/              # Mirror of source directory structure with saved images
    ├── cover.jpg
    ├── Ch. 01/
    │   ├── 001.png
    │   └── 002.png
    └── Ch. 02/
        └── 001.png
```

---

## 3. The Manifest & Source Hash Lock (`initialize_job`)

Before processing any pages, `initialize_job` establishes a cryptographic source lock:

```python
def initialize_job(cbz: Path) -> dict:
    job_dir = job_dir_for(cbz)
    manifest_path = job_dir / "manifest.json"
    source_hash = sha256_file(cbz)
    
    # 1. Verification on existing job
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["source_sha256"] != source_hash:
            raise RuntimeError(f"source CBZ changed for {cbz.name}; refusing to mix checkpoints")
        if manifest["source_name"] != cbz.name:
            raise RuntimeError(f"source filename changed for V{volume_number(cbz):02d}")
        return manifest

    # 2. Initialization of new job
    job_dir.mkdir(parents=True, exist_ok=True)
    # Validate ZIP CRC and verify all images
    ...
```

### Manifest Invariant:
If the SHA-256 hash of an input CBZ changes (e.g. file was modified or re-downloaded), the runner **refuses to mix checkpoints** and halts immediately to prevent data corruption.

---

## 4. Checkpoint Validation Logic (`valid_checkpoint`)

A checkpoint is only recognized as valid if it passes three strict gates:

```python
def valid_checkpoint(path: Path) -> bool:
    # Gate 1: Must be a regular file
    # Gate 2: File size must be greater than 0 bytes
    if not path.is_file() or path.stat().st_size == 0:
        return False
    # Gate 3: Must be a decodable, uncorrupted image
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except Exception:
        return False
```

If an interruption occurred mid-write, the truncated file will fail `valid_checkpoint` and be cleanly re-processed.

---

## 5. Atomic Disk Serialization

To guarantee that no partial files exist on disk:

### 1. Atomic JSON (`atomic_json`)
```python
def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())  # Flush OS buffers to physical disk
        os.replace(tmp_name, path)      # Atomic filesystem swap
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
```

### 2. Atomic Image Checkpoint (`save_checkpoint`)
```python
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
            check.verify()              # Verify validity before promoting
        os.replace(tmp_name, path)      # Atomic replace
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
```

---

## 6. State Machine & Lifecycle

```
[ Unstarted ]
      │
      ▼ (initialize_job)
   "ready"
      │
      ▼ (colorize_batch begins)
  "running" (updates current_entry)
      │
      ├──────────────────────────────┐
      │ (budget reached, pages left) │ (all pages completed)
      ▼                              ▼
"checkpointed"                   "complete"
                                     │
                                     ▼ (package_and_validate)
                              outputs/<volume>.cbz
```
