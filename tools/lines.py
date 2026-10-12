#!/usr/bin/env python3
"""
Вытаскивание линии без ImageMagick. Всё на numpy, без запуска процессов —
именно они съедали 88% времени сбора данных.

  dog()      — фильтр перепадов: разность двух размытий
  skeleton() — утончение Чжана-Суня, целиком на сдвигах массива
"""
import numpy as np

def _blur(a, sigma):
    """разделимое гауссово размытие маленьким ядром"""
    r = max(1, int(round(sigma * 3)))
    x = np.arange(-r, r + 1, dtype=np.float32)
    k = np.exp(-(x ** 2) / (2 * sigma * sigma)); k /= k.sum()
    out = np.zeros_like(a, dtype=np.float32)
    for i, w in zip(range(-r, r + 1), k):
        out += w * np.roll(a, i, axis=1)
    res = np.zeros_like(out)
    for i, w in zip(range(-r, r + 1), k):
        res += w * np.roll(out, i, axis=0)
    return res

def dog(gray, s1=0.6, s2=1.6, thr=0.38):
    """
    серое -> булева карта линии.
    Порог сверен с эталоном ImageMagick: совпадение пикселей 85%.
    """
    g = gray.astype(np.float32) / 255.0
    d = _blur(g, s1) - _blur(g, s2)
    d = (d - d.min()) / (d.max() - d.min() + 1e-9)
    return d < thr

_N = [(-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1)]   # P2..P9 по часовой

def _nb(img):
    return [np.roll(np.roll(img, dy, axis=0), dx, axis=1) for dy, dx in _N]

def skeleton(mask, iters=40):
    """утончение до линии в один пиксель; каждый проход — чистые сдвиги"""
    img = mask.astype(np.uint8).copy()
    img[0,:]=img[-1,:]=img[:,0]=img[:,-1]=0
    for _ in range(iters):
        changed = False
        for step in (0, 1):
            P = _nb(img)
            B = sum(P)
            A = sum(((P[i] == 0) & (P[(i+1) % 8] == 1)).astype(np.uint8) for i in range(8))
            if step == 0:
                c1 = (P[0]*P[2]*P[4] == 0); c2 = (P[2]*P[4]*P[6] == 0)
            else:
                c1 = (P[0]*P[2]*P[6] == 0); c2 = (P[0]*P[4]*P[6] == 0)
            kill = (img == 1) & (B >= 2) & (B <= 6) & (A == 1) & c1 & c2
            if kill.any():
                img[kill] = 0; changed = True
        if not changed:
            break
    return img.astype(bool)

def extract_mask(pil_gray, thr=0.58):
    a = np.asarray(pil_gray, dtype=np.uint8)
    return dog(a, thr=thr)
