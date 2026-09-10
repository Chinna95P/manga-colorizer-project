# 🎨 Manga Colorizer Project — Development Skill & Subsystem Router

This router indexes all subsystem documentation for the **Manga Colorizer Project**. When working on a task, refer to the corresponding modular documentation file under `agents/development/` for architectural rules, invariants, and implementation details.

---

## 🗂️ Subsystem Navigation Index

| Subsystem / Topic | Key Focus & Modules | Documentation File |
|---|---|---|
| **Project Overview & Workflow** | High-level pipeline architecture, environment setup, execution model, batch budgeting, and testing rules. | [`00-project-overview-and-workflow.md`](development/00-project-overview-and-workflow.md) |
| **Batch Colorization Engine** | Main runner lifecycle in `run_colorization.py`, CLI arguments, multi-volume sequential processing, and `progress.json` status updates. | [`01-batch-colorization-engine.md`](development/01-batch-colorization-engine.md) |
| **Color Detection & Passthrough** | Automatic pre-scan for colored pages, chroma/saturation math, thumbnail acceleration (144x144), threshold tuning, and passthrough checkpoints. | [`02-color-detection-and-passthrough.md`](development/02-color-detection-and-passthrough.md) |
| **Model Inference & Image Finishing** | Manga Colorization v2 loading, CWD path safety, PyTorch writable array handling, Lanczos resizing, 16% high-frequency source detail recovery, and unsharp masking. | [`03-model-inference-and-image-finishing.md`](development/03-model-inference-and-image-finishing.md) |
| **Enhancement Models & Templates** | Pipeline templates (`pipeline_templates.json`), Default Model v1, Enhanced Model v2 (2x MangaScaleV3), Enhanced Model v3 (2x IllustrationJaNai V3detail SPAN), Spandrel integration, and licenses. | [`04-enhancement-models-and-templates.md`](development/04-enhancement-models-and-templates.md) |
| **Checkpointing & Restart Safety** | Per-volume job workspaces (`workspace/jobs/V*/`), SHA-256 source lock, atomic JSON/image serialization, checkpoint validation, and state progression. | [`05-checkpointing-and-restart-safety.md`](development/05-checkpointing-and-restart-safety.md) |
| **Archive Integrity & Packaging** | Safe entry path sanitization, `ZipInfo` metadata cloning, atomic output packaging, 4-way validation (order, names, CRC, PIL verify), and `validation.json`. | [`06-archive-integrity-and-packaging.md`](development/06-archive-integrity-and-packaging.md) |
| **Utilities & Tooling** | Multithreaded color scanner (`scan_manga_colors.py`), chapter CBZ splitter (`split_cbz_into_chapters.py`), and upstream setup script (`scripts/setup_upstream.sh`). | [`07-utilities-and-tooling.md`](development/07-utilities-and-tooling.md) |

---

## ⚡ Core Invariants & Rules for AI Agents

1. **Restart Safety & Checkpoints First**: Every single processed page must be checkpointed and verified before updating status. Re-running the batch runner must seamlessly resume from the last valid checkpoint without duplicating work.
2. **Immutable Input Hash Verification**: Never mix checkpoints across modified source archives. If `source_sha256` in `manifest.json` does not match the input CBZ, halt execution immediately.
3. **Preserve Archive Structure & Ordering**: The packaged output CBZ must preserve the exact entry order, directory hierarchy, entry names, and `ZipInfo` metadata of the original source archive.
4. **Zero Data Corruption (Atomic Writes)**: All disk writes for checkpoints, manifests, status updates, and packaged CBZs must use temporary files with `fsync` and atomic rename (`os.replace`).
5. **No Blind Upstream Execution**: The upstream denoiser expects relative weight paths from `TOOL_DIR`. Ensure `os.chdir` wrapping or proper working directory management is maintained during model initialization.
6. **Writable Array Handshake**: PIL images converted to NumPy arrays can be read-only views for certain JPEGs. Always ensure explicit writable copies (`np.array(source, copy=True)`) before passing to PyTorch tensors.
7. **Color Passthrough Efficiency**: Pages with meaningful existing color (`color_fraction >= 0.15` by default) must bypass deep learning inference and be checkpointed directly as original images.
