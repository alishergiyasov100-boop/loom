#!/usr/bin/env python3
"""
Формат данных. Всё держится на одной мысли: штрих сохраняет личность.

Кадр — это список штрихов. У штриха есть id, и штрих с тем же id в соседнем
кадре — ТОТ ЖЕ САМЫЙ штрих, просто его точки сдвинулись. Поэтому промежуточный
кадр получается деформацией, а не перерисовкой, и линии нечем дрожать.

Штрих:  {"id": 7, "w": 2.0, "pts": [[x, y], ...]}      x, y в долях холста 0..1
Кадр:   {"strokes": [штрих, ...]}
Клип:   {"w": 512, "h": 512, "fps": 24, "frames": [кадр, ...]}
"""
import json, math

def stroke(sid, pts, w=2.0):
    return {"id": int(sid), "w": float(w), "pts": [[round(float(x), 4), round(float(y), 4)] for x, y in pts]}

def clip(frames, w=512, h=512, fps=24, meta=None):
    c = {"w": w, "h": h, "fps": fps, "frames": frames}
    if meta:
        c["meta"] = meta
    return c

def save(c, path):
    with open(path, "w") as f:
        json.dump(c, f, separators=(",", ":"))
    return path

def load(path):
    with open(path) as f:
        return json.load(f)

def ids_of(frame):
    return [s["id"] for s in frame["strokes"]]

def by_id(frame):
    return {s["id"]: s for s in frame["strokes"]}

def check(c):
    """Правда ли штрихи сохраняют личность и не рвутся."""
    msgs, prev = [], None
    for i, fr in enumerate(c["frames"]):
        ids = ids_of(fr)
        if len(ids) != len(set(ids)):
            msgs.append("кадр %d: повторяющиеся id" % i)
        if prev is not None:
            gone = set(prev) - set(ids)
            born = set(ids) - set(prev)
            if gone:
                msgs.append("кадр %d: исчезли %s" % (i, sorted(gone)[:6]))
            if born:
                msgs.append("кадр %d: появились %s" % (i, sorted(born)[:6]))
        prev = ids
    return msgs

def size(c):
    """Сколько весит клип в числах — это главный аргумент против пикселей."""
    n = sum(len(s["pts"]) for fr in c["frames"] for s in fr["strokes"])
    return {
        "кадров": len(c["frames"]),
        "штрихов в кадре": len(c["frames"][0]["strokes"]) if c["frames"] else 0,
        "точек всего": n,
        "чисел всего": n * 2,
    }
