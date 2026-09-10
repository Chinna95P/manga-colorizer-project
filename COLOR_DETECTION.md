# Color Detection Feature

## Overview

The pipeline now automatically detects pages that are already colored and skips colorization for them, saving processing time and GPU resources.

## How It Works

### Detection Algorithm

For each pending page (without a checkpoint):

1. **Resize to thumbnail** (144x144) for fast analysis
2. **Calculate saturation** for every pixel: `(max_channel - min_channel) / max_channel`
3. **Count colored pixels**: Pixels with saturation ≥ 0.12 and brightness ≥ 35
4. **Compute color fraction**: `colored_pixels / visible_pixels`
5. **Decision**: If `color_fraction ≥ 0.15` (default), mark as already colored

### Processing Flow

```
For each page without a checkpoint:
  ├─ Load from archive
  ├─ Measure color content
  │  ├─ If color_fraction ≥ threshold (0.15):
  │  │  └─ Create passthrough checkpoint (save original)
  │  └─ Else:
  │     └─ Add to colorization queue
  └─ Process colorization queue with model
```

## Usage

### Default Behavior (Enabled)

```bash
python run_colorization.py --device cuda --pages 50
# Automatically skips already-colored pages
```

### Disable Color Detection

```bash
python run_colorization.py --device cuda --pages 50 --no-skip-colored
# Process all pages regardless of existing color
```

### Adjust Threshold

```bash
python run_colorization.py --device cuda --pages 50 --color-threshold 0.20
# Require 20% colored pixels to skip (more conservative)

python run_colorization.py --device cuda --pages 50 --color-threshold 0.10
# Require only 10% colored pixels to skip (more aggressive)
```

## Threshold Guidelines

| Threshold | Behavior | Use Case |
|-----------|----------|----------|
| 0.10 | Aggressive | Skip pages with minimal color touches |
| 0.15 | **Default** | Balanced - skip obviously colored pages |
| 0.20 | Conservative | Only skip pages with substantial color |
| 0.25+ | Very conservative | Only skip heavily colored pages |

## Status Display

When a page is detected as already colored, the status shows:

```
running: page_name.jpg (already colored)
```

The original page is saved as-is to the checkpoint directory.

## Performance Impact

### Scanning Cost
- **Time per page**: ~5-10ms (thumbnail-based analysis)
- **Memory**: Minimal (144x144 RGB array)
- **Overhead**: Negligible compared to colorization (~2-5 seconds/page on GPU)

### Benefit
For volumes with mixed B&W and colored pages:
- Saves GPU time on already-colored pages
- Preserves original color quality (no model artifacts)
- Maintains checkpoint compatibility

## Technical Details

### Color Metrics Calculated

```python
{
  "color_fraction": 0.0-1.0,     # Fraction with saturation ≥ 0.12
  "strong_fraction": 0.0-1.0,    # Fraction with saturation ≥ 0.25
  "mean_saturation": 0.0-1.0     # Average saturation of visible pixels
}
```

### Saturation Formula

```
saturation = (max_rgb - min_rgb) / max_rgb
```

Only pixels with `max_rgb ≥ 35` are considered visible (filters pure black).

### Integration Points

1. **`measure_color_content(image)`**: Analyzes color saturation metrics
2. **`is_already_colored(image)`**: Boolean decision based on threshold
3. **`create_passthrough_checkpoint()`**: Saves original without colorization
4. **`colorize_batch()`**: Pre-scans pages, splits into passthrough/colorize queues

## Checkpoint Compatibility

- Passthrough checkpoints are identical to normal checkpoints
- Valid checkpoint = file exists, non-zero, passes PIL verify
- Resume behavior unchanged - skips all valid checkpoints
- Works with existing job directories

## Example Scenarios

### Scenario 1: Fully B&W Volume
```bash
python run_colorization.py --device cuda --pages 200
# All pages colorized, no skips
```

### Scenario 2: Mixed Volume (50% colored)
```bash
python run_colorization.py --device cuda --pages 200
# ~100 pages: passthrough (already colored)
# ~100 pages: colorized
# Total processing time: roughly half
```

### Scenario 3: Reprocessing Colored Volume
```bash
# First run (detects color, creates passthroughs)
python run_colorization.py --device cuda --pages 200

# Second run (all valid checkpoints exist, nothing to do)
python run_colorization.py --device cuda --pages 200
# Skips all pages, packages immediately
```

## Troubleshooting

### Pages Incorrectly Detected as Colored

If lightly tinted B&W pages are being skipped:
```bash
# Raise threshold to 0.20 or 0.25
python run_colorization.py --device cuda --pages 50 --color-threshold 0.25
```

### Colored Pages Not Being Detected

If colored pages are still being processed:
```bash
# Lower threshold to 0.10
python run_colorization.py --device cuda --pages 50 --color-threshold 0.10
```

### Force Reprocessing of Already-Colored Pages

```bash
# Option 1: Disable detection
python run_colorization.py --device cuda --pages 50 --no-skip-colored

# Option 2: Delete specific checkpoints
rm workspace/jobs/V01/pages/some_page.jpg
python run_colorization.py --device cuda --pages 50
```

## Future Enhancements

Potential improvements (not yet implemented):

- Per-page color metrics in manifest.json
- Batch color scan report before processing
- Different thresholds for different page types (covers vs content)
- Histogram-based color distribution analysis
- Machine learning-based color/B&W classification

---

**Added**: 2026-09-10  
**Algorithm**: Adapted from `scan_manga_colors.py`  
**Default**: Enabled with 0.15 threshold
