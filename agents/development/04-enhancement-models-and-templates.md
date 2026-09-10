# 🌟 Enhancement Models & Templates

## 1. Overview of Processing Templates

The project defines three formalized processing templates documented in `pipeline_templates.json` and `ENHANCEMENT_MODELS.md`.

```
                  ┌──────────────────────┐
                  │  Default Model v1    │
                  │  - MCv2 Stock (576p) │
                  │  - 16% Detail Blend  │
                  │  - Lanczos Restore   │
                  └──────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
┌─────────────────────────┐       ┌─────────────────────────┐
│   Enhanced Model v2     │       │   Enhanced Model v3     │
│   + 2x MangaScaleV3     │       │   + 2x IllustrationJaNai│
│   (ESRGAN+ Halftone)    │       │     V3detail SPAN-S 40k │
│   (chaiNNer Spandrel)   │       │   (chaiNNer Spandrel)   │
└─────────────────────────┘       └─────────────────────────┘
```

---

## 2. Template Specifications

### Default Model v1 (Primary / Default)
- **Role**: Standard baseline implemented in `run_colorization.py`.
- **Model**: Manga Colorization v2 stock.
- **Inference Resolution**: 576px (short dimension).
- **Denoising**: Bilateral filter active (`denoiser_sigma = 25`).
- **Post-Processing**: Original-size Lanczos restoration, 16% high-frequency source detail recovery, and restrained unsharp masking.
- **License**: MIT (pipeline code).

### Enhanced Model v2 (Opt-in: Halftone Preserving)
- **Role**: Optional 2x super-resolution upscaling stage for printed manga with visible screentones.
- **Architecture**: ESRGAN+ (64nf, 23nb).
- **Weights File**: `workspace/models/2x_MangaScaleV3.pth`
- **SHA-256**: `da2b113388bf199d69202b06d5c803d1dd85ce61955c7870f1106530a2ce142a`
- **License**: CC-BY-NC-SA-4.0
- **Primary Engine**: [chaiNNer Spandrel](https://github.com/chaiNNer-org/spandrel)
- **Characteristics**: Preserves original manga halftones and dot patterns cleanly without turning them into smudged vector artifacts.

### Enhanced Model v3 (Opt-in: Illustration / Texture Preserving)
- **Role**: Optional 2x upscaling stage optimized for colored artwork and digital manga.
- **Architecture**: SPAN (Swift Parameter-free Attention Network) — SPAN-S 40k fp16.
- **Model Family**: IllustrationJaNai v3.0.0 (Variant: V3detail).
- **Weights File**: `workspace/models/2x_IllustrationJaNai_V3detail_SPAN_S_40k_fp16.safetensors`
- **SHA-256**: `6b10bd97260ebcf639db9a961121a22c97c4f8807d43ec8a1157f3ef24b18f46`
- **License**: CC-BY-NC-4.0
- **Primary Engine**: chaiNNer Spandrel
- **Characteristics**: Fast inference, excellent edge reconstruction, retains high detail without artificial halftone smoothing.

---

## 3. Template Metadata Reference (`pipeline_templates.json`)

```json
{
  "schema": 1,
  "default_template": "Default Model v1",
  "templates": {
    "Default Model v1": {
      "role": "default",
      "colorizer": "Manga Colorization v2 stock",
      "inference_size": 576,
      "denoiser": true,
      "denoiser_sigma": 25,
      "hints": false,
      "palette_overrides": false,
      "finishing": "original-size restoration, mild source-detail recovery, Lanczos resizing, restrained sharpening"
    },
    "Enhanced Model v2": {
      "role": "opt-in",
      "base_template": "Default Model v1",
      "post_processing": {
        "model": "2x MangaScaleV3",
        "architecture": "ESRGAN+",
        "scale": 2,
        "color_mode": "RGB",
        "network": "64nf 23nb",
        "purpose": "manga upscaling with halftone retention",
        "weights": "workspace/models/2x_MangaScaleV3.pth",
        "sha256": "da2b113388bf199d69202b06d5c803d1dd85ce61955c7870f1106530a2ce142a",
        "license": "CC-BY-NC-SA-4.0",
        "primary_engine": "chaiNNer Spandrel"
      }
    },
    "Enhanced Model v3": {
      "role": "opt-in",
      "base_template": "Default Model v1",
      "post_processing": {
        "family": "IllustrationJaNai",
        "release": "3.0.0",
        "variant": "V3detail",
        "model": "2x IllustrationJaNai V3detail SPAN-S 40k",
        "architecture": "SPAN",
        "scale": 2,
        "color_mode": "RGB",
        "purpose": "detail-preserving enhancement of already-colorized manga and illustrations",
        "halftone_policy": "retain detail; no deliberate halftone cleanup",
        "weights": "workspace/models/2x_IllustrationJaNai_V3detail_SPAN_S_40k_fp16.safetensors",
        "sha256": "6b10bd97260ebcf639db9a961121a22c97c4f8807d43ec8a1157f3ef24b18f46",
        "license": "CC-BY-NC-4.0",
        "primary_engine": "chaiNNer Spandrel"
      }
    }
  }
}
```

---

## 4. Spandrel Integration Pattern

When integrating Enhanced Model v2 or v3 into a post-processing runner:

```python
import spandrel
import torch
from PIL import Image

def load_enhancement_model(weights_path: str, device: str = "cuda"):
    model = spandrel.ModelLoader().load_from_file(weights_path)
    model = model.to(device)
    model.eval()
    return model

def run_enhancement(model, pil_image: Image.Image, device: str = "cuda") -> Image.Image:
    # Convert PIL Image to PyTorch Tensor [0, 1] RGB
    tensor = spandrel.image_to_tensor(pil_image).to(device)
    with torch.no_grad():
        enhanced_tensor = model(tensor)
    return spandrel.tensor_to_image(enhanced_tensor)
```

---

## 5. Licensing & Weight Acquisition Rules

1. **No Bundling of Non-Commercial Weights**: Model weights for MangaScaleV3 (CC-BY-NC-SA-4.0) and IllustrationJaNai (CC-BY-NC-4.0) must never be committed into the git repository.
2. **Deterministic Placement**: Weights must always be placed in `workspace/models/` using exact filenames specified in the template schema.
3. **Hash Verification**: Custom loaders should verify model SHA-256 before inference to ensure weight integrity.
