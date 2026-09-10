# Manga Colorizer Project

A restart-safe CBZ manga colorization workflow built around
[Manga Colorization v2](https://github.com/qweasdd/manga-colorization-v2).
It preserves source filenames, archive entry names, folder structure, and page
order while validating every completed output.

> Use this project only with manga you own or have permission to process.
> Model files and manga pages are intentionally not included.

## Features

- Processes volume-numbered CBZ archives in deterministic volume order.
- **Automatically detects and skips already-colored pages** to save processing time.
- Saves and validates a checkpoint after every page.
- Resumes safely by skipping valid checkpoints.
- Rejects unsafe archive paths and changed input archives.
- Restores pages to their original dimensions with conservative detail recovery.
- Rebuilds CBZ files with their original filename and entry order.
- Verifies ZIP integrity, image readability, entry names, and ordering.
- Includes three documented processing templates.
- Includes optional color-scanning and chapter-splitting utilities.

## Included templates

| Template | Role | Pipeline |
| --- | --- | --- |
| Default Model v1 | Default | Manga Colorization v2 at 576 px, denoiser enabled with sigma 25, original-size restoration, mild detail recovery, Lanczos resizing, and restrained sharpening |
| Enhanced Model v2 | Opt-in | Default Model v1 followed by 2x MangaScaleV3 through Spandrel |
| Enhanced Model v3 | Opt-in | Default Model v1 followed by 2x IllustrationJaNai V3detail SPAN-S 40k through Spandrel |

The complete machine-readable definitions, model hashes, licenses, and backend
choices are in [`pipeline_templates.json`](pipeline_templates.json). Additional
selection notes are in [`ENHANCEMENT_MODELS.md`](ENHANCEMENT_MODELS.md).

The included runner implements Default Model v1. Enhanced Models v2 and v3 are
documented templates for an optional post-processing stage and require their
separately licensed weights and a compatible Spandrel-based runner.

## Requirements

- Python 3.10 or newer
- Git
- A CUDA-capable GPU is strongly recommended for large collections
- Manga Colorization v2 model weights downloaded from its upstream instructions

## Setup

```bash
git clone https://github.com/Chinna95P/manga-colorizer-project.git
cd manga-colorizer-project
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
./scripts/setup_upstream.sh
```

## Model downloads and placement

Model weights are not stored in this repository and must be downloaded
separately. Create the destination folders when needed and keep the filenames
exactly as shown.

| Template | Model file | Place it at | Required? | Download/source |
| --- | --- | --- | --- | --- |
| Default Model v1 | Generator | `workspace/manga-colorization-v2/networks/generator.zip` | Yes | [Manga Colorization v2 instructions](https://github.com/qweasdd/manga-colorization-v2#automatic-colorization) |
| Default Model v1 | Extractor | `workspace/manga-colorization-v2/networks/extractor.pth` | Yes | Included by the upstream checkout; verify that the file exists |
| Default Model v1 | Denoiser | `workspace/manga-colorization-v2/denoising/models/net_rgb.pth` | Yes | [Manga Colorization v2 instructions](https://github.com/qweasdd/manga-colorization-v2#automatic-colorization) |
| Enhanced Model v2 | 2x MangaScaleV3 | `workspace/models/2x_MangaScaleV3.pth` | Only for v2 | [OpenModelDB model page](https://openmodeldb.info/models/2x-MangaScaleV3) |
| Enhanced Model v3 | 2x IllustrationJaNai V3detail SPAN-S 40k | `workspace/models/2x_IllustrationJaNai_V3detail_SPAN_S_40k_fp16.safetensors` | Only for v3 | [MangaJaNai release 3.0.0](https://github.com/the-database/MangaJaNai/releases/tag/3.0.0) |

After downloading the Default Model v1 files, the layout must contain:

```text
workspace/manga-colorization-v2/
├── networks/generator.zip
├── networks/extractor.pth
└── denoising/models/net_rgb.pth
```

For either enhanced template, also install a compatible
[Spandrel](https://github.com/chaiNNer-org/spandrel) inference environment.
Enhanced weights use their own licenses—currently CC-BY-NC-SA-4.0 for
MangaScaleV3 and CC-BY-NC-4.0 for the listed IllustrationJaNai model—so review
those terms before use. The expected SHA-256 values and complete template
metadata are recorded in `pipeline_templates.json`.

## Colorize CBZ volumes

Place legally obtained input archives in `inputs/`. Each filename must contain a
volume marker such as `V01`, `v2`, or `V015`.

Run a small resumable batch on GPU:

```bash
python run_colorization.py --device cuda --pages 8
```

Or specify all locations explicitly:

```bash
python run_colorization.py \
  --input-dir /path/to/input-volumes \
  --jobs-dir /path/to/checkpoints \
  --output-dir /path/to/colorized-volumes \
  --device cuda \
  --pages 100
```

Run the same command again to continue. Completed archives keep the exact input
filename and are written to `outputs/` by default. Status and validation data are
stored under `workspace/jobs/` and `progress.json`.

## Optional utilities

Measure how much meaningful color is already present in each page:

```bash
python scan_manga_colors.py \
  --source /path/to/cbz-volumes \
  --output color-scan.json
```

Split colorized volumes whose pages are grouped inside `Ch. ...` folders into
separate, validated chapter archives:

```bash
python split_cbz_into_chapters.py \
  --input-dir /path/to/colorized-volumes \
  --output-dir /path/to/colorized-chapters
```

## Data and model policy

The `.gitignore` excludes manga archives, extracted pages, outputs, checkpoints,
logs, local environments, and model weights. Do not commit copyrighted manga or
third-party weights unless you have the rights and the relevant license permits
redistribution.

## License

Original code and documentation in this repository are available under the
[MIT License](LICENSE), copyright © 2026 Chinna95P.

This license does not cover Manga Colorization v2, enhancement models, other
third-party components, manga source files, or generated manga output. Those
items remain under their respective terms. See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for component-specific
licenses, restrictions, and attribution information.

## Community thanks and acknowledgements

This project depends on work shared by the open-source manga and image-restoration
communities. Thank you to:

- [qweasdd/manga-colorization-v2](https://github.com/qweasdd/manga-colorization-v2) for the core colorization model and inference code.
- [chaiNNer](https://github.com/chaiNNer-org/chaiNNer) and [Spandrel](https://github.com/chaiNNer-org/spandrel) for maintained model-loading and inference tooling.
- The [MangaScaleV3](https://openmodeldb.info/models/2x-MangaScaleV3) contributors for the manga-focused 2x enhancement model.
- [the-database/MangaJaNai](https://github.com/the-database/MangaJaNai) and the IllustrationJaNai contributors for manga and illustration enhancement models.
- [JoeyBallentine/ESRGAN](https://github.com/JoeyBallentine/ESRGAN) for the tested legacy fallback implementation.
- The wider manga colorization, restoration, and super-resolution communities for their research, testing, models, and documentation.
