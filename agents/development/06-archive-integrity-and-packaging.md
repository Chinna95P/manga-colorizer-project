# 📦 Archive Integrity & Packaging

## 1. Overview & Preservation Principles

CBZ files are ZIP archives holding image sequences. A primary design requirement of this project is **non-destructive fidelity**:
- **Entry Preservation**: Every entry (images, cover scans, metadata `.xml`/`.json`, nested folders) is preserved in exact original order.
- **Metadata Cloning**: File timestamps, compression flags, operating system attributes, and comments are cloned from source `ZipInfo` structures.
- **Path Sanitization**: Malicious archive structures (such as `../` path traversal or absolute paths `/etc/...`) are rejected before extraction.
- **Output Integrity**: Before writing to `outputs/`, the archive undergoes rigorous four-stage validation.

---

## 2. Archive Path Security (`safe_entry`)

To eliminate directory traversal vulnerabilities when processing third-party manga archives:

```python
def safe_entry(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe archive entry: {name!r}")
    return path
```

---

## 3. Metadata Cloning (`clone_zipinfo`)

When rebuilding the CBZ, default ZIP creation tools overwrite timestamps and drop compression metadata. The engine utilizes `clone_zipinfo` to maintain archival precision:

```python
def clone_zipinfo(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    clone = zipfile.ZipInfo(info.filename, date_time=info.date_time)
    for attr in (
        "compress_type", "comment", "extra", "create_system", "create_version",
        "extract_version", "reserved", "flag_bits", "volume", "internal_attr",
        "external_attr"
    ):
        setattr(clone, attr, getattr(info, attr))
    return clone
```

---

## 4. Final Packaging Pipeline (`package_and_validate`)

Once all pages in a volume have valid checkpoints (`complete == total`):

```python
def package_and_validate(cbz: Path, manifest: dict) -> Path:
    job_dir = job_dir_for(cbz)
    complete, total = progress(manifest, job_dir)
    if complete != total:
        raise RuntimeError(f"cannot package incomplete V{manifest['volume']:02d}: {complete}/{total}")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    final_path = OUTPUT_DIR / cbz.name
    
    # 1. Create temporary staging archive
    fd, tmp_name = tempfile.mkstemp(prefix=cbz.stem + ".", suffix=".cbz", dir=OUTPUT_DIR)
    os.close(fd)
    try:
        with zipfile.ZipFile(cbz, "r") as source, zipfile.ZipFile(tmp_name, "w", allowZip64=True) as target:
            for info in source.infolist():
                replacement = checkpoint_path(job_dir, info.filename)
                data = replacement.read_bytes() if valid_checkpoint(replacement) else source.read(info)
                target.writestr(clone_zipinfo(info), data)
        
        # 2. Run 4-stage validation
        validate_output(cbz, Path(tmp_name), manifest)
        
        # 3. Atomic rename into final output path
        os.replace(tmp_name, final_path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
    
    # 4. Generate validation report
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
```

---

## 5. Four-Stage Validation Protocol (`validate_output`)

Before an output CBZ is considered valid, it must pass all 4 checks:

```python
def validate_output(source_path: Path, output_path: Path, manifest: dict) -> None:
    with zipfile.ZipFile(source_path, "r") as source, zipfile.ZipFile(output_path, "r") as output:
        # Check 1: Exact entry names and ordering match source
        source_names = [info.filename for info in source.infolist()]
        output_names = [info.filename for info in output.infolist()]
        if output_names != source_names:
            raise RuntimeError("output archive entry names/order do not match input")
        
        # Check 2: ZIP CRC integrity verification
        bad = output.testzip()
        if bad:
            raise RuntimeError(f"output archive CRC failure at {bad!r}")
        
        # Check 3 & 4: Image decodability and PIL verification
        for entry in manifest["entries"]:
            if not entry["is_image"]:
                continue
            with output.open(entry["name"]) as raw, Image.open(raw) as image:
                image.verify()
```

---

## 6. Output Certification (`validation.json`)

On successful packaging, a permanent audit record is stored in the volume's job folder:

```json
{
  "archive": "Manga Title v01.cbz",
  "sha256": "4a71b2d076d2994f895db369e9a44e590499645f7823f03b22cfbb205b3837e2",
  "entry_order_preserved": true,
  "image_names_preserved": true,
  "image_count": 192,
  "zip_integrity": "passed",
  "validated_at": "2026-09-10T21:00:15+00:00"
}
```
