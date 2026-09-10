# 🚀 Project Overview & Workflow

## 1. Project Purpose & Philosophy

The **Manga Colorizer Project** is a production-grade, restart-safe manga colorization pipeline built around [Manga Colorization v2](https://github.com/qweasdd/manga-colorization-v2).

Its core objectives:
1. **Automated Batch Colorization**: Transform black-and-white CBZ manga archives into rich, vibrant colorized volumes.
2. **Preservation & Fidelity**: Retain the original archive structure, file names, internal directory hierarchy, entry order, original image dimensions, and image format (.jpg, .png).
3. **Robust Fault Tolerance**: Full restart safety where every page is checkpointed and verified, allowing interrupted batch runs to resume without recomputation or corruption.
4. **Smart Computation Skipping**: Automatically detect pre-existing color in covers, color inserts, or mixed chapters, passing them through without expensive GPU inference.

---

## 2. Directory Layout

```
manga-colorizer-project/
├── inputs/                      # Source CBZ archives with volume markers (e.g. Manga v01.cbz)
├── outputs/                     # Final validated colorized CBZ archives
├── workspace/
│   ├── manga-colorization-v2/   # Upstream model repository (git checkout)
│   │   ├── networks/
│   │   │   ├── generator.zip    # Generator weights (downloaded)
│   │   │   └── extractor.pth    # Feature extractor weights (from repo)
│   │   └── denoising/models/
│   │       └── net_rgb.pth      # Denoiser weights (downloaded)
│   ├── models/                  # Optional: Enhancement model weights (ESRGAN/SPAN)
│   └── jobs/                    # Per-volume persistent state and checkpoints
│       └── V01/
│           ├── manifest.json    # Volume metadata, SHA-256, entry table
│           ├── status.json      # Volume progress and state
│           ├── validation.json  # Output archive integrity record
│           └── pages/           # Checkpointed finished/passthrough images
├── run_colorization.py          # Primary batch runner (Default Model v1)
├── scan_manga_colors.py         # Standalone multithreaded color measurement tool
├── split_cbz_into_chapters.py  # Utility to split volume CBZs into chapter CBZs
├── pipeline_templates.json      # Machine-readable pipeline specifications
├── ENHANCEMENT_MODELS.md        # Post-processing enhancement documentation
├── COLOR_DETECTION.md           # Color detection algorithm details
├── progress.json                # Global multi-volume progress tracker
├── requirements.txt             # Python dependencies
└── scripts/
    └── setup_upstream.sh        # Automates upstream repo setup
```

---

## 3. Environment Setup & Requirements

### Dependencies
- **Python**: 3.10+
- **PyTorch**: Tested with CUDA acceleration (strongly recommended for batch colorization).
- **Pillow (PIL)**: Image loading, format conversion, unsharp masking, and integrity verification.
- **NumPy**: Matrix operations, saturation calculations, and array conversion.

### Virtual Environment Setup
```bash
cd /var/home/rpolamreddy/manga-colorizer-project
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./scripts/setup_upstream.sh
```

### Upstream Model Weight Placement
Model weights must be placed at the exact required locations:
- `workspace/manga-colorization-v2/networks/generator.zip`
- `workspace/manga-colorization-v2/networks/extractor.pth`
- `workspace/manga-colorization-v2/denoising/models/net_rgb.pth`

---

## 4. Execution Lifecycle

```
[Input CBZ in inputs/]
          │
          ▼
   Discover Volume (e.g. V01)
          │
          ▼
   Initialize Job Manifest
   - Hash SHA-256
   - Test ZIP CRC & PIL verify
   - Write workspace/jobs/V01/manifest.json
          │
          ▼
   Check Existing Checkpoints
          │
    ┌─────┴────────────────────────┐
    ▼                              ▼
All Done?                      Pending Pages
    │                              │
    │                      Pre-Scan for Color
    │                      ┌───────┴────────────────────┐
    │                      ▼                            ▼
    │               Already Colored?                B&W Page
    │                      │                            │
    │                      ▼                            ▼
    │               Passthrough Save             Run Model & Finishing
    │               (Zero GPU overhead)          (Lanczos + Blend + Unsharp)
    │                      │                            │
    │                      └────────────┬───────────────┘
    │                                   ▼
    │                          Atomic Save Checkpoint
    │                          Verify PIL Image
    │                          Update status.json & progress.json
    │                                   │
    │                      Budget Exhausted or Finished?
    │                                   │
    └───────────────────┬───────────────┘
                        ▼
            Package & Validate Final CBZ
            - Rebuild CBZ with cloned ZipInfo
            - 4-Way Validation (order, names, CRC, verify)
            - Atomic rename to outputs/
            - Write validation.json
```

---

## 5. Development Invariants for AI Engineers

1. **Do Not Modify Upstream Weight Paths Arbitrarily**: Upstream Manga Colorization v2 denoiser expects relative paths from its root; always use the wrapped loader pattern in `load_colorizer()`.
2. **Deterministic Volume Order**: Volumes must always be processed in ascending numeric order (V01, V02, V03...).
3. **Respect Memory and Checkpoints**: Before touching existing jobs in `workspace/jobs/`, inspect `status.json` and `manifest.json`. Never delete or overwrite checkpoints unless explicitly instructed to force reprocessing.
4. **Test Before Releasing**: Always test with `--pages 1` or `--pages 2` first on CPU/GPU to confirm model load and tensor pipelines before running full volumes.
