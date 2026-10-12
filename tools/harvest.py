#!/usr/bin/env python3
"""
Сбор данных: видео -> рисунки -> штрихи -> траектории -> движение групп.
Один проход на клип, всё складывается в общий набор.
"""
import sys, os, glob, math, shutil, subprocess
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from PIL import Image
from extract import extract
from track_np import track_clip

def drawings(video, work, maxn=28):
    shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
    subprocess.run(['ffmpeg','-v','error','-i',video,'-vf','scale=480:-2',
                    '-vsync','0', os.path.join(work,'%03d.png')], check=True)
    fs = sorted(glob.glob(os.path.join(work,'*.png')))
    if len(fs) < 6: return []
    sm = [np.asarray(Image.open(f).convert('L').resize((120,68)),dtype=np.int16) for f in fs]
    keep=[0]
    for i in range(1,len(sm)):
        if np.abs(sm[i]-sm[keep[-1]]).mean() >= 1.0: keep.append(i)
    # выкидываем склейки: слишком большой скачок = другой план
    out=[fs[keep[0]]]
    for i in range(1,len(keep)):
        if np.abs(sm[keep[i]]-sm[keep[i-1]]).mean() > 42: break
        out.append(fs[keep[i]])
    return out[:maxn]

def binarise_np(gray, thr=0.48):
    """линия прямо на numpy, без запуска ImageMagick"""
    from lines import dog
    return dog(gray, thr=thr)

def length(s):
    P=s['pts']; return sum(math.hypot(P[i+1][0]-P[i][0],P[i+1][1]-P[i][1]) for i in range(len(P)-1))

def resample(p, n=10):
    d=np.r_[0,np.cumsum(np.hypot(np.diff(p[:,0]),np.diff(p[:,1])))]
    if d[-1]<1e-9: return np.repeat(p[:1],n,axis=0)
    t=np.linspace(0,d[-1],n)
    return np.c_[np.interp(t,d,p[:,0]),np.interp(t,d,p[:,1])]

def one(video, nstroke=200, npts=10):
    """видео -> траектории штрихов. Целиком на numpy, без внешних процессов."""
    from lines import skeleton
    from vectorize import trace, simplify
    from track_np import dist_map, fit

    work='/tmp/h_frames_%d' % os.getpid()
    fs = drawings(video, work)
    if len(fs) < 8: return None

    gr = [np.asarray(Image.open(f).convert('L'), dtype=np.uint8) for f in fs]
    masks = [binarise_np(g) for g in gr]
    h, w = masks[0].shape

    sk = skeleton(masks[0])
    on = set(zip(*np.nonzero(sk)[::-1]))
    st = []
    for p in trace(on):
        s = simplify([(float(x), float(y)) for x, y in p], 0.8)
        if len(s) < 2: continue
        ln = sum(math.hypot(s[i+1][0]-s[i][0], s[i+1][1]-s[i][1]) for i in range(len(s)-1))
        if ln >= 4: st.append((ln, s))
    if len(st) < 40: return None
    st = [s for _, s in sorted(st, key=lambda z: -z[0])[:nstroke]]

    cur = [np.array(s, dtype=np.float64) for s in st]
    traj = [[c.copy() for c in cur]]
    ok_frac = []
    for i in range(1, len(masks)):
        dm = dist_map(masks[i])
        nxt, ok = [], 0
        for pts in cur:
            (dx, dy), c = fit(pts, dm, rng=10)
            if c <= 3.2:
                pts = pts + np.array([dx, dy]); ok += 1
            nxt.append(pts)
        ok_frac.append(ok/float(len(cur))); cur = nxt
        traj.append([c.copy() for c in cur])

    T = np.stack([np.stack([resample(p, npts) for p in fr]) for fr in traj])
    T[...,0] /= w; T[...,1] /= h
    return T, float(np.mean(ok_frac))
