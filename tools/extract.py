#!/usr/bin/env python3
"""Кадр -> штрихи, одной командой. Порог 48% подобран на настоящей генге."""
import sys, os, subprocess, json
sys.path.insert(0, os.path.dirname(__file__))
from vectorize import vectorize

def extract(src, work, thr=48, eps=1.0):
    os.makedirs(work, exist_ok=True)
    base = os.path.join(work, os.path.splitext(os.path.basename(src))[0])
    dog, binp, thin = base + "_dog.png", base + "_bin.png", base + "_thin.png"
    subprocess.run(["magick", src, "-colorspace", "Gray",
                    "-define", "convolve:scale=!", "-morphology", "Convolve", "DoG:0,0.6,1.6",
                    "-auto-level", "-negate", dog], check=True)
    subprocess.run(["magick", dog, "-threshold", "%d%%" % thr, "-negate", binp], check=True)
    subprocess.run(["magick", binp, "-negate", "-morphology", "Thinning:-1", "Skeleton", "-negate", thin], check=True)
    strokes, w, h = vectorize(thin, eps)
    return {"w": w, "h": h, "strokes": strokes}

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    r = extract(src, os.path.dirname(dst) or ".")
    json.dump({"w": r["w"], "h": r["h"], "fps": 24,
               "frames": [{"strokes": r["strokes"]}]}, open(dst, "w"), separators=(",", ":"))
    print("%s -> %d штрихов" % (os.path.basename(src), len(r["strokes"])))
