#!/usr/bin/env python3
"""
Маленькая сеть на numpy: по трём прошлым положениям штриха предсказать
следующее. Учится на том, как двигал линии живой аниматор.

Предсказываем СМЕЩЕНИЕ от последнего кадра, а не координаты — так задача
честнее и модель не может схитрить, просто скопировав вход.
"""
import numpy as np

class Net:
    def __init__(self, nin, nout, dim=256, seed=0):
        r = np.random.default_rng(seed)
        def w(a, b): return r.normal(0, np.sqrt(2.0 / a), (a, b))
        self.P = [w(nin, dim), np.zeros(dim),
                  w(dim, dim), np.zeros(dim),
                  w(dim, dim), np.zeros(dim),
                  w(dim, nout), np.zeros(nout)]
        self.m = [np.zeros_like(p) for p in self.P]
        self.v = [np.zeros_like(p) for p in self.P]
        self.t = 0

    def forward(self, x, keep=None):
        W1,b1,W2,b2,W3,b3,W4,b4 = self.P
        h1 = np.maximum(0, x @ W1 + b1)
        h2 = np.maximum(0, h1 @ W2 + b2)
        h3 = np.maximum(0, h2 @ W3 + b3)
        y  = h3 @ W4 + b4
        if keep is not None:
            keep.update(x=x, h1=h1, h2=h2, h3=h3)
        return y

    def step(self, x, target, lr=1e-3):
        c = {}
        y = self.forward(x, c)
        n = x.shape[0]
        d = (y - target) / n
        W1,b1,W2,b2,W3,b3,W4,b4 = self.P
        g = [None]*8
        g[6] = c['h3'].T @ d;  g[7] = d.sum(0)
        d3 = (d @ W4.T) * (c['h3'] > 0)
        g[4] = c['h2'].T @ d3; g[5] = d3.sum(0)
        d2 = (d3 @ W3.T) * (c['h2'] > 0)
        g[2] = c['h1'].T @ d2; g[3] = d2.sum(0)
        d1 = (d2 @ W2.T) * (c['h1'] > 0)
        g[0] = c['x'].T @ d1;  g[1] = d1.sum(0)
        self.t += 1
        b1_, b2_ = 0.9, 0.999
        for i in range(8):
            self.m[i] = b1_*self.m[i] + (1-b1_)*g[i]
            self.v[i] = b2_*self.v[i] + (1-b2_)*g[i]**2
            mh = self.m[i]/(1-b1_**self.t); vh = self.v[i]/(1-b2_**self.t)
            self.P[i] -= lr * mh/(np.sqrt(vh)+1e-8)
        return float(((y-target)**2).mean())

def windows(T, ctx=3):
    """(кадры, штрихи, точки, 2) -> примеры: вход ctx кадров, цель — смещение"""
    F, S, P, _ = T.shape
    X, Y = [], []
    for f in range(ctx, F):
        a = T[f-ctx:f]                      # (ctx, S, P, 2)
        last = T[f-1]                       # (S, P, 2)
        nxt = T[f]
        rel = a - last[None]                # всё относительно последнего кадра
        X.append(np.concatenate([rel.transpose(1,0,2,3).reshape(S, -1),
                                 last.reshape(S, -1)], axis=1))
        Y.append((nxt - last).reshape(S, -1))
    return np.concatenate(X), np.concatenate(Y)
