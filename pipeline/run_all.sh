#!/usr/bin/env bash
# Full Ganondorf avatar build: body -> outfit -> bakes -> textures ->
# collada export -> validation -> beauty renders.
#
# Usage: BLENDER=/path/to/blender pipeline/run_all.sh [output_dir]
set -euo pipefail

cd "$(dirname "$0")/.."
OUT="${1:-output}"
BLENDER="${BLENDER:-blender}"

echo "== stage 1: body =="
"$BLENDER" --background --factory-startup --python pipeline/build_body.py -- --resources assets/sl_resources --out "$OUT" 2>&1 | grep -E '^\[body\]'

echo "== stage 2: outfit =="
"$BLENDER" --background --factory-startup --python pipeline/build_outfit.py -- --out "$OUT" 2>&1 | grep -E '^\[outfit\]'

echo "== stage 3a: bakes =="
"$BLENDER" --background --factory-startup --python pipeline/bake_maps.py -- --out "$OUT" 2>&1 | grep -E '^\[bake\]'

echo "== stage 3b: textures =="
python3 pipeline/textures.py "$OUT"

echo "== stage 4: collada export =="
"$BLENDER" --background --factory-startup --python pipeline/export_dae.py -- --out "$OUT" 2>&1 | grep -E '^\[export\]'

echo "== stage 5: validation =="
python3 pipeline/validate_dae.py "$OUT" assets/sl_resources

echo "== stage 6: beauty renders =="
"$BLENDER" --background --factory-startup --python pipeline/preview_textured.py -- --out "$OUT" 2>&1 | grep -E '^\[beauty\]'

echo "== build complete =="
