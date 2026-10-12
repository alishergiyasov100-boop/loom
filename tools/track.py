#!/usr/bin/env python3
"""
Слежение вместо повторного разбора.

Главная ошибка — вытаскивать штрихи из каждого кадра заново: одна и та же
линия каждый раз рубится по-другому, и сшивать нечего. Правильно так:
разобрали ПЕРВЫЙ кадр, а дальше те же самые штрихи подтягиваем к чернилам
следующего кадра. Тогда штрих не теряет личности, количество не скачет,
и промежуточный кадр считается честно.

Два шага: сперва общий сдвиг всей картинки, потом каждая точка ищет
ближайшую линию рядом с собой, с оглядкой на соседей, чтобы штрих не рвало.
"""
import sys, os, math
from PIL import Image

def ink_map(path, thr=128):
    """чёрно-белая карта: True там, где линия"""
    im = Image.open(path).convert("L")
    w, h = im.size
    px = im.load()
    return [[px[x, y] < thr for x in range(w)] for y in range(h)], w, h

def coarse_shift(a, b, w, h, rng=12, step=2):
    """общий сдвиг: где две карты чернил совпадают лучше всего"""
    pa = [(x, y) for y in range(0, h, 3) for x in range(0, w, 3) if a[y][x]]
    best, bd = -1, (0, 0)
    for dy in range(-rng, rng + 1, step):
        for dx in range(-rng, rng + 1, step):
            hit = 0
            for x, y in pa:
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and b[yy][xx]:
                    hit += 1
            if hit > best:
                best, bd = hit, (dx, dy)
    return bd, best, len(pa)

def nearest_ink(b, w, h, x, y, r=6):
    """ближайшая точка линии в окне радиуса r"""
    xi, yi = int(round(x)), int(round(y))
    if 0 <= yi < h and 0 <= xi < w and b[yi][xi]:
        return x, y
    best, bp = None, None
    for dy in range(-r, r + 1):
        yy = yi + dy
        if yy < 0 or yy >= h:
            continue
        row = b[yy]
        for dx in range(-r, r + 1):
            xx = xi + dx
            if xx < 0 or xx >= w or not row[xx]:
                continue
            d = dx * dx + dy * dy
            if best is None or d < best:
                best, bp = d, (float(xx), float(yy))
    return bp if bp else (x, y)

def smooth(pts, k=0.3):
    """сосед тянет соседа — штрих не рвётся на куски"""
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        ax, ay = pts[i-1]
        bx, by = pts[i+1]
        out.append((px + k * ((ax + bx) / 2 - px), py + k * ((ay + by) / 2 - py)))
    out.append(pts[-1])
    return out

def fit_rigid(pts, B, w, h, rng=10):
    """
    Штрих ищет СЕБЯ целиком: пробуем сдвиги и берём тот, при котором
    больше всего его точек попадает на линию. Так штрих не рассыпается
    и не уезжает через пол-лица к чужому контуру.
    """
    best, bd = -1, (0, 0)
    for dy in range(-rng, rng + 1):
        for dx in range(-rng, rng + 1):
            hit = 0
            for x, y in pts:
                xx, yy = int(x) + dx, int(y) + dy
                if 0 <= yy < h and 0 <= xx < w and B[yy][xx]:
                    hit += 1
            if hit > best:
                best, bd = hit, (dx, dy)
    return bd, best

def track_rigid(strokes, img_a, img_b, w, h, rng=10, keep=0.34):
    """каждый штрих двигается целиком; безнадёжные остаются на месте"""
    A, _, _ = ink_map(img_a)
    B, _, _ = ink_map(img_b)
    (gx, gy), hit, tot = coarse_shift(A, B, w, h)
    out, moved, stuck = [], 0, 0
    for s in strokes:
        pts = [(p[0] * w + gx, p[1] * h + gy) for p in s["pts"]]
        (dx, dy), got = fit_rigid(pts, B, w, h, rng)
        if got < max(1, int(len(pts) * keep)):
            dx, dy = 0, 0          # опоры нет — не выдумываем движение
            stuck += 1
        else:
            moved += 1
        out.append({"id": s["id"], "w": s.get("w", 2.0),
                    "pts": [[round((x + dx) / w, 4), round((y + dy) / h, 4)] for x, y in pts]})
    return out, (gx, gy), (moved, stuck)

def track(strokes, img_a, img_b, w, h, iters=3, radius=6):
    """штрихи первого кадра -> подогнанные к второму"""
    A, _, _ = ink_map(img_a)
    B, _, _ = ink_map(img_b)
    (dx, dy), hit, tot = coarse_shift(A, B, w, h)
    out = []
    for s in strokes:
        pts = [(p[0] * w + dx, p[1] * h + dy) for p in s["pts"]]
        for _ in range(iters):
            pts = [nearest_ink(B, w, h, x, y, radius) for x, y in pts]
            pts = smooth(pts)
        out.append({"id": s["id"], "w": s.get("w", 2.0),
                    "pts": [[round(x / w, 4), round(y / h, 4)] for x, y in pts]})
    return out, (dx, dy), (hit, tot)
