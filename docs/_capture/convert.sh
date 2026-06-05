#!/usr/bin/env bash
# Convert ./_videos/*.webm into trimmed GIFs under ../assets/recordings/
set -euo pipefail
cd "$(dirname "$0")"
FF="$PWD/node_modules/@ffmpeg-installer/linux-x64/ffmpeg"
OUT=../assets/recordings; mkdir -p "$OUT"
for v in _videos/feature-*.webm; do
  base=$(basename "$v" .webm)
  dur=$("$FF" -i "$v" 2>&1 | grep -oE "Duration: [0-9:.]+" | head -1 | sed 's/Duration: //' | awk -F: '{print ($1*3600)+($2*60)+$3}')
  start=$(awk -v d="$dur" 'BEGIN{s=d-7; if(s<0)s=0; printf "%.2f", s}')
  "$FF" -ss "$start" -i "$v" -y \
    -vf "fps=11,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=96[p];[s1][p]paletteuse=dither=bayer" \
    "$OUT/$base.gif" >/dev/null 2>&1
  echo "$base -> $(du -h "$OUT/$base.gif" | cut -f1)"
done
