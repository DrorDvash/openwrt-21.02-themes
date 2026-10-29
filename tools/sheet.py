#!/usr/bin/env python3
"""Side-by-side contact sheet: sheet.py OUT.png H_CROP SCALE img1 img2 ..."""
import sys
from PIL import Image
out, hcrop, scale, files = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), sys.argv[4:]
ims = [Image.open(f).convert("RGB") for f in files]
ims = [i.crop((0, 0, i.width, min(i.height, hcrop))) for i in ims]
w = sum(i.width for i in ims) + 20 * (len(ims) - 1); h = max(i.height for i in ims)
o = Image.new("RGB", (w, h), "white"); x = 0
for i in ims:
    o.paste(i, (x, 0)); x += i.width + 20
o.resize((int(w * scale), int(h * scale))).save(out)
