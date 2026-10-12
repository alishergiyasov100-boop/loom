#!/usr/bin/env python3
"""
Сшивка штрихов между двумя рисунками — сердце всего проекта.

Если штрих из первого кадра опознан во втором, то кадр между ними это не
новый рисунок, а тот же штрих на полпути. Линия переезжает, а не
перерисовывается, и дрожать ей нечем.
"""
import sys, os, json, math

def resample(pts, n):
    """равномерно n точек вдоль ломаной, толщина переносится"""
    P = [(p[0], p[1], p[2] if len(p) > 2 else 2.0) for p in pts]
    if len(P) == 1:
        return [P[0]] * n
    seg = [math.hypot(P[i+1][0]-P[i][0], P[i+1][1]-P[i][1]) for i in range(len(P)-1)]
    total = sum(seg) or 1e-9
    out, acc, i = [], 0.0, 0
    for k in range(n):
        t = total * k / (n - 1.0)
        while i < len(seg) - 1 and acc + seg[i] < t:
            acc += seg[i]; i += 1
        f = 0.0 if seg[i] < 1e-9 else (t - acc) / seg[i]
        a, b = P[i], P[i+1]
        out.append((a[0] + (b[0]-a[0])*f, a[1] + (b[1]-a[1])*f, a[2] + (b[2]-a[2])*f))
    return out

def feats(s, n=8):
    r = resample(s["pts"], n)
    cx = sum(p[0] for p in r) / n
    cy = sum(p[1] for p in r) / n
    ln = sum(math.hypot(r[i+1][0]-r[i][0], r[i+1][1]-r[i][1]) for i in range(n-1))
    return {"r": r, "cx": cx, "cy": cy, "len": ln, "w": s.get("w", 2.0)}

def cost(fa, fb, flip=False):
    rb = list(reversed(fb["r"])) if flip else fb["r"]
    d = sum(math.hypot(a[0]-b[0], a[1]-b[1]) for a, b in zip(fa["r"], rb)) / len(rb)
    dl = abs(fa["len"] - fb["len"]) / max(1e-6, max(fa["len"], fb["len"]))
    return d + 0.25 * dl

def match(A, B, max_dist=0.06, n=8):
    FA = [feats(s, n) for s in A]
    FB = [feats(s, n) for s in B]
    pairs = []
    for i, fa in enumerate(FA):
        for j, fb in enumerate(FB):
            if abs(fa["cx"]-fb["cx"]) > max_dist or abs(fa["cy"]-fb["cy"]) > max_dist:
                continue
            c1 = cost(fa, fb, False)
            c2 = cost(fa, fb, True)
            c, fl = (c1, False) if c1 <= c2 else (c2, True)
            if c < max_dist:
                pairs.append((c, i, j, fl))
    pairs.sort()
    ua, ub, out = set(), set(), []
    for c, i, j, fl in pairs:
        if i in ua or j in ub:
            continue
        ua.add(i); ub.add(j)
        out.append({"a": i, "b": j, "flip": fl, "cost": round(c, 5)})
    return out, [i for i in range(len(A)) if i not in ua], [j for j in range(len(B)) if j not in ub]

def tween(A, B, pairs, only_a, only_b, steps=6, n=12):
    """кадры между двумя рисунками"""
    FA = {i: resample(A[i]["pts"], n) for i in range(len(A))}
    FB = {j: resample(B[j]["pts"], n) for j in range(len(B))}
    frames = []
    for k in range(steps + 2):
        t = k / float(steps + 1)
        strokes = []
        for p in pairs:
            a = FA[p["a"]]
            b = list(reversed(FB[p["b"]])) if p["flip"] else FB[p["b"]]
            pts = [[round(a[i][0] + (b[i][0]-a[i][0])*t, 4),
                    round(a[i][1] + (b[i][1]-a[i][1])*t, 4),
                    round(a[i][2] + (b[i][2]-a[i][2])*t, 2)] for i in range(n)]
            strokes.append({"id": 1000 + p["a"], "w": A[p["a"]].get("w", 2.0), "pts": pts})
        for i in only_a:          # уходящие гаснут
            if t < 0.5:
                strokes.append({"id": 2000 + i, "w": A[i].get("w", 2.0),
                                "pts": [[round(x,4), round(y,4), round(w,2)] for x, y, w in FA[i]]})
        for j in only_b:          # приходящие появляются
            if t >= 0.5:
                strokes.append({"id": 3000 + j, "w": B[j].get("w", 2.0),
                                "pts": [[round(x,4), round(y,4), round(w,2)] for x, y, w in FB[j]]})
        frames.append({"strokes": strokes})
    return frames

if __name__ == "__main__":
    a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2]))
    A = a["frames"][0]["strokes"]; B = b["frames"][0]["strokes"]
    pairs, oa, ob = match(A, B)
    print("штрихов: %d и %d" % (len(A), len(B)))
    print("сшито: %d (%.0f%% первого кадра)" % (len(pairs), 100.0*len(pairs)/max(1,len(A))))
    print("только в первом: %d, только во втором: %d" % (len(oa), len(ob)))
    steps = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    frames = tween(A, B, pairs, oa, ob, steps)
    json.dump({"w": a["w"], "h": a["h"], "fps": 24, "frames": frames},
              open(sys.argv[3], "w"), separators=(",", ":"))
    print("кадров с промежуточными: %d -> %s" % (len(frames), sys.argv[3]))
