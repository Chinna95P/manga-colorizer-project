#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
checkout="$project_root/workspace/manga-colorization-v2"

if [[ -e "$checkout" ]]; then
  echo "Upstream checkout already exists: $checkout"
else
  mkdir -p "$project_root/workspace"
  git clone https://github.com/qweasdd/manga-colorization-v2.git "$checkout"
fi

echo
echo "Manga Colorization v2 is ready at: $checkout"
echo "Download its model weights by following:"
echo "https://github.com/qweasdd/manga-colorization-v2#automatic-colorization"
echo
echo "Required files:"
echo "  $checkout/networks/generator.zip"
echo "  $checkout/networks/extractor.pth"
echo "  $checkout/denoising/models/net_rgb.pth"
