#!/usr/bin/env python3
"""
Растр -> штрихи.

Берём скелет линии толщиной в один пиксель и проходим по нему как по дорожкам:
от каждого конца и каждой развилки идём вперёд, пока дорожка не кончится.
Получается набор ломаных — это и есть штрихи. Потом упрощаем, чтобы точек
было не больше, чем нужно глазу.
"""
import sys, os, json, math
from PIL import Image

N8 = [(-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)]

def load_skeleton(path, thr=128):
    im = Image.open(path).convert("L")
    w, h = im.size
    px = im.load()
    on = set()
    for y in range(h):
        for x in range(w):
            if px[x, y] < thr:
                on.add((x, y))
    return on, w, h

def neighbours(p, on):
    x, y = p
    return [(x+dx, y+dy) for dx, dy in N8 if (x+dx, y+dy) in on]

def trace(on):
    """
    Ломаные по скелету. На развилке НЕ останавливаемся, а идём туда, где
    линия продолжается прямее — человек ведёт штрих сквозь пересечения,
    а не бросает его там. Иначе рисунок рассыпается на обрывки.
    """
    deg = {p: len(neighbours(p, on)) for p in on}
    ends = [p for p in on if deg[p] == 1]
    nodes = [p for p in on if deg[p] >= 3]
    used = set()
    paths = []

    def straightest(prev, cur, cands):
        vx, vy = cur[0] - prev[0], cur[1] - prev[1]
        L = math.hypot(vx, vy) or 1.0
        vx, vy = vx / L, vy / L
        best, bq = -2.0, None
        for q in cands:
            wx, wy = q[0] - cur[0], q[1] - cur[1]
            M = math.hypot(wx, wy) or 1.0
            dot = (vx * wx + vy * wy) / M
            if dot > best:
                best, bq = dot, q
        return bq if best > 0.1 else None     # резкий разворот — это другой штрих

    def walk(start, first):
        path = [start, first]
        used.add(frozenset((start, first)))
        cur, prev = first, start
        while True:
            cands = [q for q in neighbours(cur, on)
                     if q != prev and frozenset((cur, q)) not in used]
            if not cands:
                break
            q = cands[0] if len(cands) == 1 else straightest(prev, cur, cands)
            if q is None:
                break
            used.add(frozenset((cur, q)))
            path.append(q)
            prev, cur = cur, q
            if deg.get(cur, 0) == 1:
                break
        return path

    for s in ends + nodes:
        for n in neighbours(s, on):
            if frozenset((s, n)) in used:
                continue
            paths.append(walk(s, n))

    for p in on:                      # остатки: замкнутые кольца без концов
        for n in neighbours(p, on):
            if frozenset((p, n)) not in used:
                paths.append(walk(p, n))
    return [p for p in paths if len(p) >= 4]

def simplify(pts, eps=1.2):
    """Дуглас-Пекер: выкидываем точки, которые ничего не меняют"""
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    dx, dy = b[0]-a[0], b[1]-a[1]
    L = math.hypot(dx, dy) or 1e-9
    worst, wi = 0.0, 0
    for i in range(1, len(pts)-1):
        px, py = pts[i]
        d = abs(dy*px - dx*py + b[0]*a[1] - b[1]*a[0]) / L
        if d > worst:
            worst, wi = d, i
    if worst <= eps:
        return [a, b]
    return simplify(pts[:wi+1], eps)[:-1] + simplify(pts[wi:], eps)

def widths_from(distmap):
    """карта расстояний до фона: в скелете это ровно половина толщины линии"""
    if not distmap or not os.path.exists(distmap):
        return None
    im = Image.open(distmap).convert("L")
    return im.load(), im.size

def vectorize(path, eps=1.2, min_len=6, width=1.8, distmap=None):
    on, w, h = load_skeleton(path)
    raw = trace(on)
    dm = widths_from(distmap)
    out = []
    for i, p in enumerate(raw):
        s = simplify([(float(x), float(y)) for x, y in p], eps)
        if len(s) < 2:
            continue
        ln = sum(math.hypot(s[k+1][0]-s[k][0], s[k+1][1]-s[k][1]) for k in range(len(s)-1))
        if ln < min_len:
            continue
        pts = []
        for x, y in s:
            if dm:
                px, (dw, dh) = dm
                xx = min(dw - 1, max(0, int(round(x))))
                yy = min(dh - 1, max(0, int(round(y))))
                t = max(1.0, px[xx, yy] * 2.0)      # радиус -> толщина
            else:
                t = width
            pts.append([round(x / w, 4), round(y / h, 4), round(t, 2)])
        avg = sum(q[2] for q in pts) / len(pts)
        out.append({"id": len(out) + 1, "w": round(avg, 2), "pts": pts})
    return out, w, h

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    eps = float(sys.argv[3]) if len(sys.argv) > 3 else 1.2
    dmap = sys.argv[4] if len(sys.argv) > 4 else None
    strokes, w, h = vectorize(src, eps, distmap=dmap)
    clip = {"w": w, "h": h, "fps": 24, "frames": [{"strokes": strokes}],
            "meta": {"from": os.path.basename(src)}}
    json.dump(clip, open(dst, "w"), separators=(",", ":"))
    pts = sum(len(s["pts"]) for s in strokes)
    print("штрихов: %d, точек: %d, в среднем %.1f точки на штрих" % (len(strokes), pts, pts/max(1,len(strokes))))
