# 🛠️ Utilities & Tooling

## 1. Overview of Utility Suite

In addition to the primary batch runner, the repository includes specialized tools for analyzing image color and splitting processed volumes.

```
manga-colorizer-project/
├── scan_manga_colors.py         # Multithreaded color metric profiler
├── split_cbz_into_chapters.py  # Hierarchy extractor & chapter CBZ builder
└── scripts/
    └── setup_upstream.sh        # Automates git checkout & directory preparation
```

---

## 2. Color Profiler (`scan_manga_colors.py`)

`scan_manga_colors.py` scans a directory of CBZ archives across multiple threads to assess how much existing color is present in each volume and page before running colorization.

### Usage
```bash
python scan_manga_colors.py --source inputs/ --output color-scan.json --workers 8
```

### CLI Arguments
- `--source`: Path to folder containing `.cbz` files.
- `--output`: Path to output `.json` report file.
- `--workers`: Number of parallel thread pool workers (defaults to `min(6, os.cpu_count())`).

### Algorithm & Schema
Uses concurrent `ThreadPoolExecutor` to process archives. For every image:
1. Resizes to 144x144 thumbnail.
2. Evaluates saturation: $(max - min) / max$.
3. Masks pixels with $high \ge 35.0$.
4. Computes `color_fraction` (saturation $\ge 0.12$), `strong_fraction` ($\ge 0.25$), and `mean_saturation`.

### Output JSON Format
```json
{
  "schema": 1,
  "source": "/var/home/rpolamreddy/manga-colorizer-project/inputs",
  "total_pages": 402,
  "archives": [
    {
      "archive": "Manga Title v01.cbz",
      "pages": [
        {
          "name": "cover.jpg",
          "mode": "RGB",
          "color_fraction": 0.842105,
          "strong_fraction": 0.710526,
          "mean_saturation": 0.485123
        },
        {
          "name": "Ch. 01/001.png",
          "mode": "L",
          "color_fraction": 0.0,
          "strong_fraction": 0.0,
          "mean_saturation": 0.0
        }
      ]
    }
  ]
}
```

---

## 3. Chapter Splitter (`split_cbz_into_chapters.py`)

When manga volumes are organized internally with chapter folders (e.g., `Ch. 01/`, `Ch. 02/`, `Chapter 12/`), this tool splits the volume CBZs into standalone chapter CBZs while preserving metadata and page ordering.

### Usage
```bash
python split_cbz_into_chapters.py \
  --input-dir outputs/ \
  --output-dir outputs-by-chapter/
```

### Architecture & Safety Invariants
1. **Chapter Regex Matching**: Identifies chapter folder components matching `r"\bCh\.\s*\d"` (case-insensitive).
2. **Path Re-rooting**: Strips the volume root and re-roots images cleanly into the root of the chapter archive.
3. **Atomic Staging Directory**: Writes to a `.in-progress` staging folder; only renames to `output_dir` upon 100% successful completion.
4. **Per-Chapter Validation**: Every generated chapter CBZ undergoes CRC verification and entry order checking before promotion.
5. **Manifest Generation**: Generates `manifest.json` inside the output directory summarizing source volumes, chapter count, and page totals.

### Splitting Process
```python
component_index, chapter = chapter_component(info.filename)
parts = PurePosixPath(info.filename).parts
member_name = PurePosixPath(*parts[component_index + 1:]).as_posix()
chapters.setdefault(chapter, []).append((info, member_name))
```

---

## 4. Setup Script (`scripts/setup_upstream.sh`)

Automates submodule/upstream setup and ensures workspace folders exist:

```bash
./scripts/setup_upstream.sh
```

### Actions Performed:
1. Clones `https://github.com/qweasdd/manga-colorization-v2.git` into `workspace/manga-colorization-v2/` if missing.
2. Displays weight placement instructions and download URLs.
