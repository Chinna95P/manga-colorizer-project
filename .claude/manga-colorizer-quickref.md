# Manga Colorizer Project - Quick Reference

A project-specific skill for common manga colorization operations.

## Commands

### Setup and Initialization

Initialize the project environment:

```bash
cd /var/home/rpolamreddy/manga-colorizer-project
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./scripts/setup_upstream.sh
```

### Colorization Operations

**Start or resume a colorization batch:**

```bash
# Process up to 50 pages on GPU
python run_colorization.py --device cuda --pages 50

# Process on CPU (slower but works without CUDA)
python run_colorization.py --device cpu --pages 10

# Full explicit paths
python run_colorization.py \
  --input-dir /path/to/volumes \
  --jobs-dir /path/to/checkpoints \
  --output-dir /path/to/output \
  --device cuda \
  --pages 100
```

**Check batch progress:**

```bash
cat progress.json | jq .
# Shows completed_volumes, total_volumes, and per-volume status
```

**Check specific volume status:**

```bash
cat workspace/jobs/V01/status.json | jq .
# Shows state, completed_pages, total_pages, timestamps
```

### Utilities

**Scan for existing color saturation:**

```bash
python scan_manga_colors.py --source inputs/ --output color-scan.json
# Measures how much meaningful color already exists in pages
```

**Split volumes into chapters:**

```bash
python split_cbz_into_chapters.py \
  --input-dir outputs/ \
  --output-dir outputs-by-chapter/
# Splits volumes with "Ch. NN" folder structure into separate archives
```

## Project Structure

```
inputs/              # Place source CBZ volumes here (must have V01, v2, etc. markers)
outputs/             # Completed colorized volumes
workspace/
  ├── manga-colorization-v2/    # Upstream model (git submodule)
  │   ├── networks/
  │   │   ├── generator.zip     # Download required
  │   │   └── extractor.pth     # From upstream
  │   └── denoising/models/
  │       └── net_rgb.pth       # Download required
  ├── models/                   # Optional enhancement model weights
  └── jobs/                     # Per-volume checkpoints
      └── V01/
          ├── manifest.json
          ├── status.json
          ├── validation.json
          └── pages/            # Checkpointed images
progress.json        # Overall batch status
```

## Pipeline Templates

**Default Model v1** (implemented in run_colorization.py):
- Manga Colorization v2 at 576px inference
- Denoiser enabled (sigma 25)
- Original-size restoration with Lanczos
- Mild detail recovery (16% blend)
- Restrained sharpening

**Enhanced Model v2** (template only, requires separate runner):
- Base pipeline + 2x MangaScaleV3
- License: CC-BY-NC-SA-4.0

**Enhanced Model v3** (template only, requires separate runner):
- Base pipeline + 2x IllustrationJaNai V3detail
- License: CC-BY-NC-4.0

## Troubleshooting

**Model files missing:**
Download required weights per README.md:
- Generator and denoiser from Manga Colorization v2 upstream
- Place in exact paths shown above

**CUDA out of memory:**
- Reduce batch size: `--pages 5`
- Use CPU: `--device cpu`
- Close other GPU-using applications

**Archive validation failed:**
- Check source CBZ integrity with any ZIP tool
- Ensure filename has volume marker (V01, v2, V015, etc.)
- Don't modify source archives during processing

**Checkpoint appears stuck:**
- Check `workspace/jobs/V*/status.json` for current state
- Invalid checkpoints are automatically skipped on restart
- Safe to kill and restart - validated work is never redone

## Key Features

- **Restart-safe**: Re-run the same command to resume
- **Validated**: Every page checkpoint and output verified
- **Deterministic**: Volumes processed in numeric order
- **Preservative**: Maintains archive structure, entry names, ordering

## References

- Repository: https://github.com/Chinna95P/manga-colorizer-project
- Full documentation: See CLAUDE.md and README.md in project root
- Model specs: pipeline_templates.json
- Model selection rationale: ENHANCEMENT_MODELS.md
