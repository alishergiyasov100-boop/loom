#!/usr/bin/env python3
"""
Модель. Задача одна: по нескольким прошедшим кадрам предсказать следующий.

Кадр представлен как вектор фиксированной длины: штрихи идут в порядке id,
у каждого штриха фиксированное число точек, каждая точка это x и y. Пока
состав штрихов постоянен — это полигон, здесь так и есть. Переменный состав
(штрихи появляются и исчезают) добавим, когда базовое предсказание заработает.

Запускать на Kaggle: torch там уже стоит.
"""
import json, glob, os, math, argparse

def frame_vec(frame, order, npts):
    v = []
    byid = {s["id"]: s for s in frame["strokes"]}
    for sid in order:
        s = byid[sid]
        pts = s["pts"]
        for i in range(npts):
            t = i * (len(pts) - 1) / float(npts - 1)
            a, b = int(t), min(int(t) + 1, len(pts) - 1)
            f = t - a
            v.append(pts[a][0] * (1 - f) + pts[b][0] * f)
            v.append(pts[a][1] * (1 - f) + pts[b][1] * f)
    return v

def vec_frame(v, order, npts, widths):
    out = []
    k = 0
    for sid in order:
        pts = []
        for _ in range(npts):
            pts.append([v[k], v[k + 1]]); k += 2
        out.append({"id": sid, "w": widths.get(sid, 2.0), "pts": pts})
    return {"strokes": out}

def load_set(folder, npts=16, ctx=3):
    """вход: ctx кадров, выход: следующий кадр"""
    X, Y, meta = [], [], None
    for f in sorted(glob.glob(os.path.join(folder, "*.json"))):
        c = json.load(open(f))
        frames = c["frames"]
        order = sorted(s["id"] for s in frames[0]["strokes"])
        widths = {s["id"]: s["w"] for s in frames[0]["strokes"]}
        if meta is None:
            meta = {"order": order, "npts": npts, "widths": widths, "w": c["w"], "h": c["h"], "fps": c["fps"]}
        vs = [frame_vec(fr, order, npts) for fr in frames]
        for i in range(len(vs) - ctx):
            X.append(vs[i:i + ctx]); Y.append(vs[i + ctx])
    return X, Y, meta

def main():
    import torch, torch.nn as nn
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/synth")
    ap.add_argument("--out", default="out/model.pt")
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--ctx", type=int, default=3)
    ap.add_argument("--npts", type=int, default=16)
    ap.add_argument("--dim", type=int, default=256)
    a = ap.parse_args()

    X, Y, meta = load_set(a.data, a.npts, a.ctx)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    X = torch.tensor(X, dtype=torch.float32, device=dev)
    Y = torch.tensor(Y, dtype=torch.float32, device=dev)
    n_in = X.shape[1] * X.shape[2]
    n_out = Y.shape[1]
    print("примеров %d, вход %d чисел, выход %d, устройство %s" % (len(X), n_in, n_out, dev))

    model = nn.Sequential(
        nn.Flatten(),
        nn.Linear(n_in, a.dim), nn.GELU(),
        nn.Linear(a.dim, a.dim), nn.GELU(),
        nn.Linear(a.dim, a.dim), nn.GELU(),
        nn.Linear(a.dim, n_out),
    ).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, a.epochs)
    lossf = nn.SmoothL1Loss(beta=0.01)

    cut = max(1, int(len(X) * 0.85))
    for ep in range(a.epochs):
        model.train()
        p = model(X[:cut]); loss = lossf(p, Y[:cut])
        opt.zero_grad(); loss.backward(); opt.step(); sched.step()
        if ep % 50 == 0 or ep == a.epochs - 1:
            model.eval()
            with torch.no_grad():
                vl = lossf(model(X[cut:]), Y[cut:]).item() if len(X) > cut else float("nan")
                px = (model(X[cut:]) - Y[cut:]).abs().mean().item() * meta["w"] if len(X) > cut else float("nan")
            print("эпоха %4d  обучение %.5f  проверка %.5f  средняя ошибка %.2f пикселя" % (ep, loss.item(), vl, px))

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    torch.save({"state": model.state_dict(), "meta": meta, "n_in": n_in, "n_out": n_out, "dim": a.dim, "ctx": a.ctx}, a.out)
    print("сохранил", a.out)

if __name__ == "__main__":
    main()
