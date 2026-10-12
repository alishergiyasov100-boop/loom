#!/usr/bin/env python3
"""Штрихи -> картинки -> видео. Чтобы смотреть глазами, а не верить на слово."""
import sys, os, subprocess
sys.path.insert(0, os.path.dirname(__file__))
import strokes as S
from PIL import Image, ImageDraw

def draw_frame(frame, w, h, bg=(255, 255, 255), ink=(20, 20, 22), ghost=None):
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    if ghost:
        for g in ghost:
            for st in g["strokes"]:
                pts = [(p[0] * w, p[1] * h) for p in st["pts"]]
                d.line(pts, fill=(205, 203, 200), width=max(1, int(st["w"])), joint="curve")
    for st in frame["strokes"]:
        P = st["pts"]
        has_w = len(P[0]) > 2
        if not has_w:
            pts = [(p[0] * w, p[1] * h) for p in P]
            d.line(pts, fill=ink, width=max(1, int(round(st["w"] * w / 256.0))), joint="curve")
            continue
        # толщина своя у каждой точки — рисуем по отрезкам с кружками в стыках
        for i in range(len(P) - 1):
            a = (P[i][0] * w, P[i][1] * h)
            b = (P[i+1][0] * w, P[i+1][1] * h)
            t = max(1.0, (P[i][2] + P[i+1][2]) / 2.0)
            t = min(t, 9.0)
            d.line([a, b], fill=ink, width=int(round(t)))
            r = t / 2.0
            d.ellipse([a[0]-r, a[1]-r, a[0]+r, a[1]+r], fill=ink)
        last = (P[-1][0] * w, P[-1][1] * h)
        r = min(max(1.0, P[-1][2]), 9.0) / 2.0
        d.ellipse([last[0]-r, last[1]-r, last[0]+r, last[1]+r], fill=ink)
    return im

def render(clip, outdir, onion=0):
    os.makedirs(outdir, exist_ok=True)
    w, h, frames = clip["w"], clip["h"], clip["frames"]
    for i, fr in enumerate(frames):
        gh = frames[max(0, i - onion):i] if onion else None
        draw_frame(fr, w, h, ghost=gh).save(os.path.join(outdir, "%03d.png" % i))
    return len(frames)

def video(outdir, path, fps):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
                    "-i", os.path.join(outdir, "%03d.png"),
                    "-vf", "format=yuv420p", path], check=True)
    return path

if __name__ == "__main__":
    c = S.load(sys.argv[1])
    out = sys.argv[2]
    onion = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    n = render(c, out, onion)
    video(out, out.rstrip("/") + ".mp4", c["fps"])
    print("кадров %d -> %s.mp4  (%dx%d, %d fps)" % (n, out.rstrip("/"), c["w"], c["h"], c["fps"]))
