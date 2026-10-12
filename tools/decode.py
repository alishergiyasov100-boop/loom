#!/usr/bin/env python3
"""Кадры из спрайт-листа в PNG. Материал для проверки глаза."""
import json, sys, os
from PIL import Image

def load(path):
    with open(path) as f:
        return json.load(f)

def rgba(c):
    if c == "transparent":
        return (0, 0, 0, 0)
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)

def frames(sheet, anim):
    a = next(x for x in sheet["anims"] if x["name"] == anim)
    pal = [rgba(c) for c in sheet["pal"]]
    out = []
    for rows in a["frames"]:
        im = Image.new("RGBA", (sheet["w"], sheet["h"]), (0, 0, 0, 0))
        px = im.load()
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                i = int(ch, 36)
                if i:
                    px[x, y] = pal[i] if i < len(pal) else (255, 0, 255, 255)
        out.append(im)
    return out, a.get("fps", 8)

if __name__ == "__main__":
    data = load(sys.argv[1])
    who, anim, outdir = sys.argv[2], sys.argv[3], sys.argv[4]
    scale = int(sys.argv[5]) if len(sys.argv) > 5 else 8
    os.makedirs(outdir, exist_ok=True)
    ims, fps = frames(data[who], anim)
    for i, im in enumerate(ims):
        big = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
        big.save(os.path.join(outdir, "%03d.png" % i))
    print("кадров: %d, исходный fps: %s -> %s" % (len(ims), fps, outdir))
