#!/usr/bin/env python3
"""
Глаз. Модель не видит свою анимацию — значит покажем ей.

Из папки кадров делает три картинки, по которым можно судить о движении,
и видео на нужной частоте:

  contact.png  — все кадры сеткой с номерами, видно рисунок каждого
  onion.png    — онион-скин: каждый кадр поверх соседей, видно интервалы
  trail.png    — след движения: где вообще менялись пиксели за цикл
  move.mp4     — как это выглядит вживую

Ничего не додумывает: если кадров мало, это будет видно.
"""
import os, sys, glob, subprocess
from PIL import Image, ImageDraw, ImageChops

def load(d):
    fs = sorted(glob.glob(os.path.join(d, "*.png")))
    if not fs:
        raise SystemExit("нет кадров в " + d)
    return [Image.open(f).convert("RGBA") for f in fs], fs

def flat(im, bg=(255, 255, 255, 255)):
    b = Image.new("RGBA", im.size, bg)
    b.alpha_composite(im)
    return b

def contact(ims, out, cols=8, pad=6, label=True):
    w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    cw, ch = w + pad * 2, h + pad * 2 + (14 if label else 0)
    sheet = Image.new("RGBA", (cw * min(cols, len(ims)), ch * rows), (246, 245, 243, 255))
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        x, y = (i % cols) * cw, (i // cols) * ch
        d.rectangle([x + 2, y + 2, x + cw - 3, y + ch - 3], outline=(222, 220, 216, 255))
        sheet.alpha_composite(flat(im), (x + pad, y + pad))
        if label:
            d.text((x + pad, y + h + pad + 1), "%d" % i, fill=(120, 118, 114, 255))
    sheet.save(out)
    return sheet.size

def onion(ims, out, back=2, pad=6):
    """каждый кадр поверх предыдущих — так аниматор смотрит интервалы"""
    w, h = ims[0].size
    sheet = Image.new("RGBA", ((w + pad) * len(ims) + pad, h + pad * 2 + 16), (246, 245, 243, 255))
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        cell = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        for k in range(max(0, i - back), i):
            ghost = ims[k].copy()
            a = ghost.getchannel("A").point(lambda v, k=k, i=i: int(v * (0.22 + 0.12 * (k - i + back))))
            ghost.putalpha(a)
            cell.alpha_composite(ghost)
        cell.alpha_composite(im)
        sheet.alpha_composite(cell, (pad + i * (w + pad), pad))
        d.text((pad + i * (w + pad), h + pad + 2), "%d" % i, fill=(120, 118, 114, 255))
    sheet.save(out)

def trail(ims, out):
    """где за цикл вообще что-то двигалось — дыры в движении видно сразу"""
    w, h = ims[0].size
    acc = Image.new("L", (w, h), 0)
    for a, b in zip(ims, ims[1:] + ims[:1]):
        diff = ImageChops.difference(flat(a).convert("L"), flat(b).convert("L"))
        acc = ImageChops.lighter(acc, diff)
    heat = Image.merge("RGB", (acc.point(lambda v: 255 - v), acc.point(lambda v: 255 - v // 2), Image.new("L", (w, h), 255)))
    heat.save(out)

def video(frames_dir, out, fps):
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", str(fps), "-pattern_type", "glob", "-i", os.path.join(frames_dir, "*.png"),
        "-vf", "scale=iw:ih:flags=neighbor,format=yuv420p", "-r", str(fps), out
    ], check=True)

def report(ims, fps):
    """сухие числа, по которым видно, хватает ли кадров"""
    n = len(ims)
    moved = []
    for a, b in zip(ims, ims[1:] + ims[:1]):
        diff = ImageChops.difference(flat(a).convert("L"), flat(b).convert("L"))
        moved.append(sum(1 for p in diff.getdata() if p > 24))
    secs = n / float(fps)
    lines = [
        "кадров: %d" % n,
        "на %d fps это %.2f с движения" % (fps, secs),
        "чтобы занять секунду при %d fps, нужно %d" % (fps, fps),
        "смена между кадрами (пикселей): " + " ".join(str(m) for m in moved),
    ]
    if moved:
        hi, lo = max(moved), min(moved)
        if hi and lo / float(hi) < 0.45:
            lines.append("интервалы рваные: самый большой скачок в %.1f раза больше самого малого" % (hi / max(1.0, lo)))
    return "\n".join(lines)

if __name__ == "__main__":
    d = sys.argv[1]
    out = sys.argv[2]
    fps = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    os.makedirs(out, exist_ok=True)
    ims, _ = load(d)
    contact(ims, os.path.join(out, "contact.png"))
    onion(ims, os.path.join(out, "onion.png"))
    trail(ims, os.path.join(out, "trail.png"))
    video(d, os.path.join(out, "move.mp4"), fps)
    txt = report(ims, fps)
    open(os.path.join(out, "report.txt"), "w").write(txt)
    print(txt)
