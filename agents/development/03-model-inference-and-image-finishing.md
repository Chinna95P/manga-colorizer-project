# 🧠 Model Inference & Image Finishing

## 1. Upstream Model Integration

The project integrates [Manga Colorization v2](https://github.com/qweasdd/manga-colorization-v2) by *qweasdd*, an adversarial network designed specifically for automatic manga colorization with built-in denoising.

### Upstream Model Components
- **Generator**: `workspace/manga-colorization-v2/networks/generator.zip`
- **Feature Extractor**: `workspace/manga-colorization-v2/networks/extractor.pth`
- **Bilateral Denoiser**: `workspace/manga-colorization-v2/denoising/models/net_rgb.pth`

---

## 2. Model Loading & CWD Safety Invariant

### The CWD Dependency Bug in Upstream
The upstream denoiser module internally resolves its model weight paths relative to the current working directory (`os.getcwd()`). If the script is invoked from the project root rather than the submodule directory, model initialization will fail with a file-not-found error.

### The Working Directory Wrapper Solution
`run_colorization.py` safely wraps model loading with temporary directory switching:

```python
def load_colorizer():
    sys.path.insert(0, str(TOOL_DIR))
    from colorizator import MangaColorizator
    # The upstream denoiser resolves its weight path relative to the process CWD.
    previous_cwd = Path.cwd()
    try:
        os.chdir(TOOL_DIR)
        return MangaColorizator(
            DEVICE,
            str(TOOL_DIR / "networks" / "generator.zip"),
            str(TOOL_DIR / "networks" / "extractor.pth"),
        )
    finally:
        os.chdir(previous_cwd)
```

---

## 3. Tensor Conversion & Writable Array Invariant

### PyTorch Writable Memory Requirement
When PIL opens certain JPEG images, `np.asarray(image)` or `np.array(image)` may yield a read-only memory view. When PyTorch or the upstream denoiser attempts to wrap or modify this buffer into a `torch.Tensor`, it can trigger a runtime error (`ValueError: output array is read-only` or memory layout mismatch).

### The Invariant Implementation
The engine explicitly forces a writable copy of the image array before ingestion:

```python
# PIL can expose a read-only NumPy view for some JPEGs; the upstream
# denoiser converts it to a tensor, so provide an explicitly writable copy.
colorizer.set_image(np.array(source, copy=True), 576, True, 25)
```

### Colorizer Parameters
- `image`: Writable RGB NumPy array.
- `size`: `576` (short-side inference resolution).
- `denoise`: `True` (bilateral color denoising).
- `denoiser_sigma`: `25` (standard manga compression noise threshold).

---

## 4. Post-Inference Finishing Pipeline (`finish_image`)

Raw model output from neural colorization is returned at 576px resolution with floating point values in `[0.0, 1.0]`. The finishing pipeline restores original dimensions and structure while preventing blurriness.

```
Model Output (576px, [0, 1])
          │
          ▼
   Convert to RGB PIL Image (clip [0, 255])
          │
          ▼
   Lanczos Resample to Original Source Dimensions
          │
          ▼
   Extract High-Frequency Source Detail
   - source_gray = source.convert("L")
   - low_freq = source_gray.filter(GaussianBlur(radius=1.0))
   - detail = source_gray - low_freq
          │
          ▼
   Blend 16% Source Detail onto Predicted Color Array
   - color_array += detail[..., None] * 0.16
          │
          ▼
   Apply Restrained Unsharp Mask
   - UnsharpMask(radius=0.65, percent=35, threshold=3)
          │
          ▼
   Final Finished Image
```

### Python Implementation
```python
def finish_image(source: Image.Image, model_rgb: np.ndarray) -> Image.Image:
    # 1. Scale predicted color map to source dimensions
    predicted = Image.fromarray(np.clip(model_rgb * 255.0, 0, 255).astype(np.uint8), "RGB")
    predicted = predicted.resize(source.size, Image.Resampling.LANCZOS)

    # 2. Recover high-frequency source structure without replacing model chroma
    source_gray = source.convert("L")
    low = source_gray.filter(ImageFilter.GaussianBlur(radius=1.0))
    detail = np.asarray(source_gray, dtype=np.float32) - np.asarray(low, dtype=np.float32)
    color = np.asarray(predicted, dtype=np.float32)
    color += detail[..., None] * 0.16
    
    # 3. Clip and apply subtle unsharp mask
    finished = Image.fromarray(np.clip(color, 0, 255).astype(np.uint8), "RGB")
    return finished.filter(ImageFilter.UnsharpMask(radius=0.65, percent=35, threshold=3))
```

### Finishing Parameter Rationale
- **16% Detail Blend (`0.16`)**: Injects line crispness and screentone texture from the high-res original scan without causing harsh halos or desaturating colors.
- **Gaussian Blur (`radius=1.0`)**: Isolates fine line art and screentones from low-frequency page shading.
- **Unsharp Mask (`radius=0.65, percent=35, threshold=3`)**: Adds subtle edge definition while avoiding sharpening noise or compression grain.
