#!/usr/bin/env python3
"""
Слежение за штрихами на numpy. То же, что раньше, но в сотни раз быстрее:
вместо перебора пикселей в питоне считаем карту расстояний до линии один
раз, а дальше каждый штрих ищет себя по ней сдвигами.
"""
import numpy as np
from PIL import Image

def ink(path, thr=128):
    a = np.asarray(Image.open(path).convert("L"))
    return (a < thr)

def dist_map(mask, maxd=14):
    """грубая карта расстояний: сколько шагов до ближайшей линии"""
    d = np.full(mask.shape, maxd, dtype=np.int16)
    d[mask] = 0
    for _ in range(maxd):
        s = d.copy()
        s[1:, :]  = np.minimum(s[1:, :],  d[:-1, :] + 1)
        s[:-1, :] = np.minimum(s[:-1, :], d[1:, :] + 1)
        s[:, 1:]  = np.minimum(s[:, 1:],  d[:, :-1] + 1)
        s[:, :-1] = np.minimum(s[:, :-1], d[:, 1:] + 1)
        if np.array_equal(s, d):
            break
        d = s
    return d

def _probe(points, dmap, offs):
    """все сдвиги сразу: одна выборка по карте вместо цикла"""
    h, w = dmap.shape
    px = points[:, 0][None, :]; py = points[:, 1][None, :]
    ox = offs[:, 0][:, None]; oy = offs[:, 1][:, None]
    xx = np.clip((px + ox).astype(np.int32), 0, w - 1)
    yy = np.clip((py + oy).astype(np.int32), 0, h - 1)
    return dmap[yy, xx].mean(axis=1)

def fit(points, dmap, rng=12, step=1):
    """
    Грубо-точный поиск: сначала крупным шагом по всей области,
    потом уточнение вокруг найденного. Проб в шесть раз меньше.
    """
    g = np.arange(-rng, rng + 1, 3)
    offs = np.array([(dx, dy) for dy in g for dx in g], dtype=np.float64)
    c = _probe(points, dmap, offs)
    i = int(np.argmin(c)); cx, cy = offs[i]
    f = np.arange(-2, 3)
    offs2 = np.array([(cx + dx, cy + dy) for dy in f for dx in f], dtype=np.float64)
    c2 = _probe(points, dmap, offs2)
    j = int(np.argmin(c2))
    return (float(offs2[j][0]), float(offs2[j][1])), float(c2[j])

def track_clip(strokes, frame_paths, rng=12, good=3.0):
    """
    Штрихи первого кадра протаскиваются через весь кусок.
    Возвращает траектории: для каждого кадра — положение каждого штриха.
    """
    masks = [ink(p) for p in frame_paths]
    h, w = masks[0].shape
    base = [np.array([[p[0] * w, p[1] * h] for p in s["pts"]], dtype=np.float64) for s in strokes]
    traj = [[b.copy() for b in base]]
    cur = [b.copy() for b in base]
    quality = []
    for i in range(1, len(masks)):
        dm = dist_map(masks[i])
        nxt, ok = [], 0
        for pts in cur:
            (dx, dy), c = fit(pts, dm, rng)
            if c <= good:
                pts = pts + np.array([dx, dy], dtype=np.float64)
                ok += 1
            nxt.append(pts)
        quality.append(ok / float(len(cur)))
        cur = nxt
        traj.append([p.copy() for p in cur])
    return traj, (w, h), quality
