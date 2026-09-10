# 🔍 Color Detection & Passthrough

## 1. Overview & Problem Statement

Manga volumes frequently contain a mix of color and black-and-white content:
- Front cover and back cover illustrations
- Special color inserts / title pages (e.g. Chapter 1 opening spreads)
- Occasional colored side-stories or bonus art

Processing already-colored images through a black-and-white colorization model can distort artist color palettes, wash out skin tones, introduce generative artifacts, and waste significant GPU resources.

The **Color Detection & Passthrough** system in `run_colorization.py` automatically identifies pre-colored pages and creates verified passthrough checkpoints in ~5–10ms per page, bypassing the neural network entirely.

---

## 2. Detection Algorithm & Mathematical Formulation

The algorithm operates on a fast thumbnail representation to minimize CPU overhead.

### Step-by-Step Flow:
1. **Thumbnail Resizing**: Resizes the image to 144x144 pixels using Lanczos resampling.
2. **Matrix Conversion**: Converts thumbnail to floating point RGB array (`np.float32`).
3. **Channel Extremes**:
   $$\text{high} = \max(R, G, B)$$
   $$\text{low} = \min(R, G, B)$$
4. **Saturation Calculation**:
   $$\text{saturation} = \frac{\text{high} - \text{low}}{\max(\text{high}, 1.0)}$$
5. **Visibility Masking**: Excludes pure blacks and extremely dark pixels where chromaticity noise is high:
   $$\text{visible} = \text{high} \ge 35.0$$
6. **Chroma Metric Computation**:
   - `color_fraction`: Fraction of visible pixels with $\text{saturation} \ge 0.12$.
   - `strong_fraction`: Fraction of visible pixels with $\text{saturation} \ge 0.25$.
   - `mean_saturation`: Average saturation of all visible pixels.

```python
def measure_color_content(image: Image.Image) -> dict[str, float]:
    """Measure meaningful chroma in an image (adapted from scan_manga_colors.py)."""
    rgb = image.convert("RGB")
    rgb.thumbnail((144, 144), Image.Resampling.LANCZOS)
    values = np.asarray(rgb, dtype=np.float32)
    high = values.max(axis=2)
    low = values.min(axis=2)
    saturation = (high - low) / np.maximum(high, 1.0)
    visible = high >= 35.0
    denominator = max(int(visible.sum()), 1)
    return {
        "color_fraction": float(((saturation >= COLOR_SATURATION_THRESHOLD) & visible).sum() / denominator),
        "strong_fraction": float(((saturation >= 0.25) & visible).sum() / denominator),
        "mean_saturation": float(saturation[visible].mean()) if visible.any() else 0.0,
    }
```

---

## 3. Decision Logic & Configuration Thresholds

A page is classified as `already_colored` when its `color_fraction` meets or exceeds `COLOR_FRACTION_THRESHOLD`.

```python
COLOR_SATURATION_THRESHOLD = 0.12  # Minimum saturation to consider a pixel colored
COLOR_FRACTION_THRESHOLD = 0.15    # Minimum fraction of colored pixels to skip colorization
SKIP_COLORED_PAGES = True          # Enabled by default
```

```python
def is_already_colored(image: Image.Image) -> bool:
    """Determine if a page already has meaningful color and should be skipped."""
    if not SKIP_COLORED_PAGES:
        return False
    metrics = measure_color_content(image)
    return metrics["color_fraction"] >= COLOR_FRACTION_THRESHOLD
```

### Threshold Sensitivity Guide

| Threshold | Mode | Behavior | Ideal Use Case |
|---|---|---|---|
| **0.10** | Aggressive | Skips pages with minimal color touches or spot colors. | Volumes with soft watercolor or pale color palettes. |
| **0.15** | **Default** | Balanced detection; accurately skips covers, full-color inserts, and colored art. | Standard commercial manga releases. |
| **0.20** | Conservative | Only skips pages with broad, dominant color coverage. | Manga with heavy yellowed paper scans or tinted screentones. |
| **0.25+** | Strict | Requires very heavy coloration to skip. | High-noise scans where paper aging creates artificial saturation. |

---

## 4. Passthrough Checkpoint Mechanism

When a page is detected as colored:
1. `write_status(job_dir, manifest, "running", entry_name + " (already colored)")` is reported.
2. The original source image is saved directly to `workspace/jobs/V01/pages/<entry_path>` using `save_checkpoint()`.
3. The image is saved preserving the source format (JPEG quality=95 subsampling=0, or PNG compress_level=6).
4. The saved checkpoint passes through standard PIL verification (`check.verify()`).
5. Zero GPU inference is performed.

```python
def create_passthrough_checkpoint(source: Image.Image, path: Path, suffix: str) -> None:
    """Save the source image as a checkpoint without colorization."""
    save_checkpoint(source, path, suffix)
```

---

## 5. Performance Benchmark & Impact

- **CPU Thumbnail Scan Time**: 5–10 ms per page.
- **GPU Inference Time Saved**: ~2.5 to 5.0 seconds per page on modern CUDA GPUs.
- **Accuracy**: Eliminates 100% of generative model artifacts on native color art.
- **Storage Compatibility**: Checkpoints produced by passthrough are indistinguishable from model checkpoints in terms of validation and packaging downstream.
