#!/usr/bin/env bash
# Uso: render_png.sh <entrada.svg> <salida.png>  -> PNG 1200x1200
set -u
in=$1; out=$2
ok(){ [ -s "$out" ] && head -c 8 "$out" | od -An -c | grep -q 'P   N   G' && { echo "PNG OK ($1)"; exit 0; }; }
command -v rsvg-convert >/dev/null && rsvg-convert -w 1200 -h 1200 "$in" -o "$out" 2>/dev/null && ok rsvg-convert
python3 -c "import cairosvg" 2>/dev/null || pip install -q cairosvg >/dev/null 2>&1
python3 -c "import cairosvg,sys;cairosvg.svg2png(url=sys.argv[1],write_to=sys.argv[2],output_width=1200,output_height=1200)" "$in" "$out" 2>/dev/null && ok cairosvg
for m in magick convert; do command -v $m >/dev/null && $m -background none -density 144 "$in" -resize 1200x1200 "$out" 2>/dev/null && ok $m; done
command -v chromium >/dev/null && chromium --headless --disable-gpu --screenshot="$out" --window-size=1200,1200 "file://$(realpath "$in")" 2>/dev/null && ok chromium
python3 -c "import playwright" 2>/dev/null || { pip install -q playwright >/dev/null 2>&1 && python3 -m playwright install --with-deps chromium >/dev/null 2>&1; }
python3 - "$in" "$out" <<'PY' 2>/dev/null && ok playwright
import sys,pathlib
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1200,"height":1200})
    pg.goto(pathlib.Path(sys.argv[1]).resolve().as_uri()); pg.screenshot(path=sys.argv[2]); b.close()
PY
echo "ERROR: no se pudo convertir el SVG a PNG" >&2; exit 1
