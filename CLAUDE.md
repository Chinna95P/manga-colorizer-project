# Manga Colorizer Project

## Project Overview

This is a production-quality manga colorization pipeline built around [Manga Colorization v2](https://github.com/qweasdd/manga-colorization-v2). It processes CBZ manga archives with full restart safety, checkpoint validation, and deterministic ordering.

**Purpose**: Automatically colorize black-and-white manga volumes while preserving archive structure, entry names, page order, and original dimensions.

**Status**: Active development project with documented templates and tested workflows.

## Key Principles

- **Restart-safe**: Every page is checkpointed and validated; re-running the same command continues where it left off
- **Smart Color Detection**: Automatically detects already-colored pages and marks them as valid checkpoints without reprocessing
- **Deterministic**: Processes volumes in numeric order (V01, V02, etc.)
- **Preservative**: Maintains original filenames, ZIP entry names, folder structure, and page order
- **Validated**: Every output is integrity-checked for ZIP structure, image readability, entry order, and naming

## Architecture

### Core Pipeline (Default Model v1)

1. **Input**: Volume-numbered CBZ archives (e.g., `Manga Title v01.cbz`)
2. **Colorization**: Manga Colorization v2 at 576px inference size
   - Denoiser enabled (sigma 25)
   - No manual hints or palette overrides
3. **Finishing**: 
   - Restore to original dimensions using Lanczos resizing
   - Mild source-detail recovery (16% detail blend with 1.0px Gaussian blur)
   - Restrained sharpening (UnsharpMask: radius=0.65, percent=35, threshold=3)
4. **Output**: Validated CBZ with original filename and structure

### Optional Enhancement Models

- **Enhanced Model v2**: Base pipeline + 2x MangaScaleV3 upscaling
  - Preserves halftones, trained specifically for manga
  - Requires separate Spandrel runner
  - License: CC-BY-NC-SA-4.0

- **Enhanced Model v3**: Base pipeline + 2x IllustrationJaNai V3detail
  - SPAN architecture optimized for colored manga/illustrations
  - Retains texture and detail without halftone cleanup
  - Requires separate Spandrel runner
  - License: CC-BY-NC-4.0

## Project Structure

```
manga-colorizer-project/
├── inputs/              # Place source CBZ volumes here
├── outputs/             # Completed colorized volumes appear here
├── workspace/
│   ├── manga-colorization-v2/   # Upstream model (git submodule)
│   │   ├── networks/
│   │   │   ├── generator.zip    # Download separately
│   │   │   └── extractor.pth    # From upstream
│   │   └── denoising/models/
│   │       └── net_rgb.pth      # Download separately
│   ├── models/          # Optional: enhancement model weights
│   └── jobs/            # Per-volume checkpoints and manifests
│       └── V01/
│           ├── manifest.json
│           ├── status.json
│           ├── validation.json
│           └── pages/   # Checkpointed colorized pages
├── run_colorization.py  # Main batch runner
├── scan_manga_colors.py # Utility: measure existing color
├── split_cbz_into_chapters.py  # Utility: split by chapter folders
├── pipeline_templates.json      # Machine-readable template specs
├── ENHANCEMENT_MODELS.md        # Model selection rationale
└── progress.json        # Overall batch status
```

## Common Workflows

### Initial Setup

```bash
cd /var/home/rpolamreddy/manga-colorizer-project
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./scripts/setup_upstream.sh
```

Then download the required model weights (see README.md "Model downloads and placement").

### Colorize a Batch

```bash
# Small batch on GPU
python run_colorization.py --device cuda --pages 8

# Continue where you left off
python run_colorization.py --device cuda --pages 50

# Process on CPU (slower)
python run_colorization.py --device cpu --pages 5
```

### Check Progress

```bash
cat progress.json
# Shows: completed_volumes, total_volumes, per-volume status
```

### Scan for Existing Color

Before colorizing, check if pages already have meaningful color:

```bash
python scan_manga_colors.py --source inputs/ --output color-scan.json
```

### Split by Chapters

If volumes have internal `Ch. NN` folder structure:

```bash
python split_cbz_into_chapters.py \
  --input-dir outputs/ \
  --output-dir outputs-by-chapter/
```

## Technical Details

### Restart Safety

Each volume gets a job directory (`workspace/jobs/V01/`) with:
- **manifest.json**: Source archive SHA-256, entry list, CRCs, pipeline config
- **status.json**: Current state, completed/total pages, timestamps
- **pages/**: Directory tree matching archive structure with checkpointed images
- **validation.json**: Final output hash and integrity report

The runner:
1. Refuses to continue if source archive SHA-256 changes
2. Validates every checkpoint before considering it complete
3. Skips valid checkpoints on restart
4. Only packages the output CBZ when all pages are complete

### Image Processing Details

- **Inference size**: 576px (smaller dimension)
- **Denoising**: Enabled with sigma=25 to reduce compression artifacts
- **Detail recovery**: Extracts high-frequency structure from grayscale source, blends at 16% strength
- **Sharpening**: Conservative UnsharpMask to restore crispness after resizing
- **Format preservation**: Maintains original file extension (.jpg, .png, etc.)
- **Quality**: JPEG at quality=95, subsampling=0; PNG at compress_level=6

### Volume Discovery

Input CBZs must have volume markers: `V01`, `v2`, `V015`, etc.
- Parsed via regex: `\bv(\d{1,3})\b` (case-insensitive)
- Processed in numeric order
- Duplicate volume numbers are rejected

### ZIP Archive Safety

- Rejects absolute paths and `..` in entry names
- Preserves original ZipInfo metadata (timestamps, compression, external attributes)
- Validates CRC integrity on input and output
- Tests every image entry with PIL verify
- Maintains exact entry order from source archive

## Model Licenses

- **Manga Colorization v2**: Check upstream repository for license
- **Default Model v1 finishing code**: MIT (this repository)
- **2x MangaScaleV3**: CC-BY-NC-SA-4.0
- **2x IllustrationJaNai V3detail**: CC-BY-NC-4.0
- **Manga source files and generated output**: Not covered; respect copyright

## Dependencies

- Python 3.10+
- PyTorch (CUDA support recommended)
- Pillow (PIL)
- NumPy
- Manga Colorization v2 (git submodule)
- Optional: Spandrel/chaiNNer for enhancement models

## Key Files Reference

| File | Purpose |
|------|---------|
| `run_colorization.py` | Main batch runner implementing Default Model v1 |
| `pipeline_templates.json` | Formal template definitions with hashes and licenses |
| `ENHANCEMENT_MODELS.md` | Model selection rationale and alternatives reviewed |
| `scan_manga_colors.py` | Utility to measure existing color saturation |
| `split_cbz_into_chapters.py` | Utility to split volumes into chapter archives |
| `progress.json` | Real-time batch status (auto-generated) |
| `workspace/jobs/V*/manifest.json` | Per-volume source metadata and pipeline config |
| `workspace/jobs/V*/status.json` | Per-volume progress tracking |

## Development Notes

- The project uses atomic file writes (write-to-temp, then replace) for all JSON and image outputs
- Checkpoints are validated before being considered complete (file exists, non-zero, PIL verify passes)
- The upstream denoiser resolves paths relative to CWD, so the runner temporarily changes directory during model load
- PIL can return read-only NumPy arrays for some JPEGs; the runner explicitly copies to writable arrays before passing to the model

## Future Considerations

- Integration of enhanced models (v2/v3) into the main runner
- Parallel page processing for multi-GPU systems
- Automatic page reordering detection and correction
- Support for CBR (RAR) archives
- Web UI for batch management and preview

---

**Repository**: https://github.com/Chinna95P/manga-colorizer-project  
**License**: MIT (original code); see THIRD_PARTY_NOTICES.md for dependencies  
**Last Updated**: 2026-09-10
