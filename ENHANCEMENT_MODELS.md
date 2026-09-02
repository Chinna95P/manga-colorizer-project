# Manga enhancement model assessment

## Selected for Enhanced Model v2

**2x MangaScaleV3** is the approved post-processing model. It is an ESRGAN+
RGB model trained on a custom manga dataset to upscale manga while retaining
halftones. Its 2x scale fits the existing Enhanced Model v2 definition without
the previous waifu2x stage.

Primary engine: chaiNNer's maintained Spandrel loader/runtime.

Fallback engine: JoeyBallentine/ESRGAN at commit
`dd240633384d02efe511079d7207b6711536b3c2`. The fallback successfully loaded
and ran MangaScaleV3, but its upstream repository states that it is no longer
actively maintained.

## Manga-focused alternatives reviewed

- **IllustrationJaNai**: adopted as Enhanced Model v3 because it is trained for
  colored manga images and illustrations. The selected current-release model is
  `2x_IllustrationJaNai_V3detail_SPAN_S_40k_fp16.safetensors`. V3detail retains
  texture and does not clean halftone noise; the 2x SPAN-S network is directly
  supported by Spandrel and is suitable for the project's 6 GB GPU.
- **MangaJaNai**: highly specialized for black-and-white digital manga, with
  models selected by source page height. It is not the default choice after
  Default Model v1 because that input is already colored.
- **Real-CUGAN**: useful for manga/anime restoration and compression cleanup,
  but less specifically aligned with preserving the existing colorized output
  and halftone treatment than MangaScaleV3.
- **KurehaMangaSR/LiloScale**: newer experimental manga models using DAT/ATD;
  their own project warns that screentones can become noisy during experimental
  training, so they are not selected as a stable project default.

Future model changes should be made only after an A/B test on representative
pages containing faces, gradients, dense screentones, fine line art, and text.

## References

- https://openmodeldb.info/models/2x-MangaScaleV3
- https://github.com/chaiNNer-org/chaiNNer
- https://github.com/chaiNNer-org/spandrel
- https://github.com/JoeyBallentine/ESRGAN
- https://github.com/the-database/MangaJaNai
- https://github.com/the-database/MangaJaNai/releases
- https://github.com/lunarpham/MangaUpscalingModels
