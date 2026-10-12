#!/usr/bin/env python3
"""
Синтетический полигон.

Рисуем простое существо из штрихов и двигаем его по известным законам.
Соответствие штрихов между кадрами тут идеальное по построению — именно
поэтому на нём честно проверяется, учится ли модель вообще. Не научится
здесь, где данные без единой ошибки, — не научится нигде.
"""
import math, random, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import strokes as S

def circle(cx, cy, r, n=16):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]

def bone(a, b, bend=0.0, n=5):
    """кость с лёгким изгибом — чтобы штрих был кривой, а не отрезком"""
    ax, ay = a; bx, by = b
    nx, ny = -(by - ay), (bx - ax)
    L = math.hypot(nx, ny) or 1.0
    nx, ny = nx / L, ny / L
    out = []
    for i in range(n):
        t = i / (n - 1.0)
        k = math.sin(math.pi * t) * bend
        out.append((ax + (bx - ax) * t + nx * k, ay + (by - ay) * t + ny * k))
    return out

def figure(t, kind="walk", phase=0.0):
    """
    Существо: голова, корпус, две руки, две ноги. Постоянные id у штрихов.
    t — доля цикла 0..1
    """
    a = 2 * math.pi * (t + phase)
    cx = 0.5
    bob = 0.012 * math.sin(2 * a) if kind == "walk" else 0.0
    if kind == "bounce":
        cy = 0.52 + 0.14 * abs(math.sin(a))
        squash = 1.0 - 0.22 * max(0.0, math.cos(a))
    else:
        cy = 0.52 + bob
        squash = 1.0

    hip = (cx, cy)
    sho = (cx, cy - 0.17 * squash)
    head_c = (cx, sho[1] - 0.075 * squash)

    sw = 0.0 if kind == "bounce" else 1.0
    la = math.sin(a) * 0.5 * sw
    ra = -la
    ll = -la
    rl = la

    out = []
    out.append(S.stroke(1, circle(head_c[0], head_c[1], 0.055 * squash), 2.2))
    out.append(S.stroke(2, bone(sho, hip, 0.01 * math.sin(a) * sw), 2.6))
    out.append(S.stroke(3, bone(sho, (sho[0] - 0.10 + la * 0.06, sho[1] + 0.13), -0.02 + la * 0.03), 2.0))
    out.append(S.stroke(4, bone(sho, (sho[0] + 0.10 + ra * 0.06, sho[1] + 0.13), 0.02 + ra * 0.03), 2.0))
    out.append(S.stroke(5, bone(hip, (hip[0] - 0.05 + ll * 0.12, hip[1] + 0.21), -0.015 + ll * 0.02), 2.4))
    out.append(S.stroke(6, bone(hip, (hip[0] + 0.05 + rl * 0.12, hip[1] + 0.21), 0.015 + rl * 0.02), 2.4))
    if kind == "wave":
        out[3] = S.stroke(4, bone(sho, (sho[0] + 0.12, sho[1] - 0.12 + 0.05 * math.sin(4 * a)), 0.03), 2.0)
    return {"strokes": out}

def make(kind="walk", frames=24, seed=0):
    random.seed(seed)
    ph = random.random()
    fr = [figure(i / float(frames), kind, ph) for i in range(frames)]
    return S.clip(fr, 512, 512, 24, {"kind": kind, "seed": seed})

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "data/synth"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    os.makedirs(out, exist_ok=True)
    kinds = ["walk", "bounce", "wave"]
    made = 0
    for i in range(n):
        k = kinds[i % len(kinds)]
        c = make(k, 24, seed=i)
        bad = S.check(c)
        if bad:
            print("пропустил", i, bad[:2]); continue
        S.save(c, os.path.join(out, "%s_%03d.json" % (k, i)))
        made += 1
    print("сделал клипов:", made, "->", out)
    print("размер одного:", S.size(make("walk", 24)))
