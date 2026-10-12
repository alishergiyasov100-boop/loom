#!/usr/bin/env python3
"""
Десять секунд: стойка — заметил — замах — рывок — удар — отдача — возврат.
Позы задаются углами, между ними интервалы с разным характером.
"""
import math, sys, os, copy
sys.path.insert(0, os.path.dirname(__file__))
import strokes as S
from figure import draw, DEF

def ease_out(t):  return 1 - (1 - t) ** 3
def ease_in(t):   return t * t * t
def smooth(t):    return t * t * (3 - 2 * t)
def snap(t):      return 1 - (1 - t) ** 6          # почти мгновенно

FPS = 24
def P(**kw):
    p = dict(DEF); p.update(kw); return p

KEYS = [
    (  0, P(), 'smooth'),
    ( 34, P(hipy=0.545, spine=-1.60, head_tilt=0.06), 'smooth'),      # дыхание
    ( 54, P(hipy=0.540, spine=-1.52, head_tilt=-0.22, armR=2.25, foreR=2.0), 'ease_out'),  # заметил
    ( 76, P(hipy=0.545, spine=-1.44, head_tilt=-0.16, armR=2.55, foreR=3.0,
            armL=1.05, foreL=1.1, thighR=1.95, shinR=1.5), 'ease_out'),   # замах
    ( 96, P(hipy=0.550, spine=-1.38, head_tilt=-0.10, armR=2.75, foreR=3.5,
            armL=0.95, foreL=1.0, thighR=2.05, shinR=1.42, squash=0.97), 'ease_out'),  # крайний замах
    (104, P(hipy=0.555, spine=-1.50, head_tilt=-0.02, armR=2.5, foreR=3.1,
            armL=1.0, foreL=1.05, thighR=1.98, shinR=1.46, squash=1.04), 'ease_in'),  # сжатие
    (111, P(hipx=0.44, hipy=0.545, spine=-1.72, head_tilt=0.10, armR=0.55, foreR=0.35,
            armL=1.9, foreL=2.1, thighR=1.5, shinR=1.6, thighL=1.2, shinL=1.35,
            squash=1.10, scale=1.92), 'snap'),                              # УДАР
    (115, P(hipx=0.455, hipy=0.552, spine=-1.66, head_tilt=0.16, armR=0.62, foreR=0.44,
            armL=1.85, foreL=2.0, thighR=1.55, shinR=1.58, thighL=1.25, shinL=1.38,
            squash=0.90), 'ease_out'),                                      # попадание
    (134, P(hipx=0.48, hipy=0.548, spine=-1.58, head_tilt=0.08, armR=1.5, foreR=1.5,
            armL=1.4, foreL=1.5), 'ease_out'),                              # отдача
    (176, P(hipy=0.542, spine=-1.56, head_tilt=0.02), 'smooth'),            # возврат
    (216, P(hipy=0.545, spine=-1.58, head_tilt=0.04), 'smooth'),            # выдох
    (240, P(), 'smooth'),
]
IMPACT = 115
EASE = dict(smooth=smooth, ease_out=ease_out, ease_in=ease_in, snap=snap)

def pose_at(f):
    for i in range(len(KEYS) - 1):
        f0, a, _ = KEYS[i]; f1, b, mode = KEYS[i + 1]
        if f0 <= f <= f1:
            t = 0.0 if f1 == f0 else (f - f0) / float(f1 - f0)
            e = EASE[mode](t)
            return {k: a[k] + (b[k] - a[k]) * e for k in a}
    return dict(KEYS[-1][1])

def build():
    frames, hist = [], []
    for f in range(241):
        p = pose_at(f)
        if IMPACT <= f <= IMPACT + 3:
            p = dict(p); p["hipx"] += 0.010 * (1 - (f - IMPACT) / 4.0) * (1 if f % 2 else -1)
        hl = (0.0, 0.0); cl = (0.0, 0.0)
        if len(hist) >= 3:
            hl = (p["hipx"] - hist[-3][0], p["hipy"] - hist[-3][1])
        if len(hist) >= 5:
            cl = (p["hipx"] - hist[-5][0], p["hipy"] - hist[-5][1])
        sm = None
        if len(hist) >= 1:
            dx = abs(p["hipx"] - hist[-1][0]) + abs(p["armR"] - hist[-1][2]) * 0.05
            if dx > 0.035:
                from figure import skeleton
                prev_j = skeleton(hist[-1][3]); cur_j = skeleton(p)
                sm = (prev_j["hndR"], cur_j["hndR"])
        fr, j = draw(p, hair_lag=hl, coat_lag=cl, smear=sm)
        if IMPACT <= f <= IMPACT + 2:
            k = f - IMPACT
            hx, hy = j["hndR"]
            for i in range(12):
                a = i * math.pi / 6 + k * 0.18
                r0 = 0.030 + k * 0.022; r1 = r0 + 0.055 - k * 0.013
                fr["strokes"].append(S.stroke(200 + i,
                    [(hx + r0*math.cos(a), hy + r0*math.sin(a)),
                     (hx + r1*math.cos(a), hy + r1*math.sin(a))], 2.8))
        hist.append((p["hipx"], p["hipy"], p["armR"], p))
        frames.append(fr)
    return S.clip(frames, 480, 480, FPS, {"shot": "10 секунд"})

if __name__ == "__main__":
    c = build()
    S.save(c, sys.argv[1] if len(sys.argv) > 1 else "data/shot10.json")
    print("кадров %d, %.1f секунды" % (len(c["frames"]), len(c["frames"]) / float(FPS)))
