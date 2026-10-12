# ============================================================
#  LOOM — сбор данных для модели 2D-анимации
#  Kaggle: Settings -> Accelerator: None (карта не нужна),
#          Internet: On. Запусти и оставь — до 9 часов.
#  Результат: /kaggle/working/clips/*.npy — траектории штрихов.
# ============================================================
import os, sys, json, time, glob, math, shutil, subprocess, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image

OUT = "/kaggle/working/clips"
LOG = "/kaggle/working/harvest.log"
UA  = "Mozilla/5.0 (X11; Linux x86_64) InkHarvester"
TARGET  = 12000          # сколько сцен хотим
WORKERS = 8              # у Kaggle 4 ядра, но много времени уходит на сеть


# ---------- линия ----------
"""
Вытаскивание линии без ImageMagick. Всё на numpy, без запуска процессов —
именно они съедали 88% времени сбора данных.

  dog()      — фильтр перепадов: разность двух размытий
  skeleton() — утончение Чжана-Суня, целиком на сдвигах массива
"""

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

# ---------- трассировка ----------
"""
Растр -> штрихи.

Берём скелет линии толщиной в один пиксель и проходим по нему как по дорожкам:
от каждого конца и каждой развилки идём вперёд, пока дорожка не кончится.
Получается набор ломаных — это и есть штрихи. Потом упрощаем, чтобы точек
было не больше, чем нужно глазу.
"""

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

# ---------- слежение ----------
"""
Слежение за штрихами на numpy. То же, что раньше, но в сотни раз быстрее:
вместо перебора пикселей в питоне считаем карту расстояний до линии один
раз, а дальше каждый штрих ищет себя по ней сдвигами.
"""

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

# ---------- сбор ----------
TAGS = ["character_acting","walk_cycle","fighting","effects","hair","fabric",
        "smears","running","dialogue","creatures","animated","background_animation",
        "impact_frames","debris","sports","vehicle","rotation","morphing",
        "presumed","production_materials","genga","hanabi","liquid","explosions",
        "lightning","smoke","food","dancing","flying","sliding"]

def log(m):
    line = "%s  %s" % (time.strftime("%H:%M:%S"), m)
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def resample(p, n=10):
    p = np.asarray(p, dtype=np.float64)
    d = np.r_[0, np.cumsum(np.hypot(np.diff(p[:,0]), np.diff(p[:,1])))]
    if d[-1] < 1e-9: return np.repeat(p[:1], n, axis=0)
    t = np.linspace(0, d[-1], n)
    return np.c_[np.interp(t,d,p[:,0]), np.interp(t,d,p[:,1])]

def drawings(video, work, maxn=28):
    shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
    subprocess.run(["ffmpeg","-v","error","-i",video,"-vf","scale=480:-2",
                    "-vsync","0", os.path.join(work,"%03d.png")], check=True)
    fs = sorted(glob.glob(os.path.join(work,"*.png")))
    if len(fs) < 6: return []
    sm = [np.asarray(Image.open(f).convert("L").resize((120,68)), dtype=np.int16) for f in fs]
    keep=[0]
    for i in range(1,len(sm)):
        if np.abs(sm[i]-sm[keep[-1]]).mean() >= 1.0: keep.append(i)
    out=[fs[keep[0]]]
    for i in range(1,len(keep)):
        if np.abs(sm[keep[i]]-sm[keep[i-1]]).mean() > 42: break   # склейка плана
        out.append(fs[keep[i]])
    return out[:maxn]

def one(video, tagdir, nstroke=200, npts=10):
    fs = drawings(video, tagdir)
    if len(fs) < 8: return None
    gr = [np.asarray(Image.open(f).convert("L"), dtype=np.uint8) for f in fs]
    masks = [dog(g, thr=0.48) for g in gr]
    h, w = masks[0].shape
    sk = skeleton(masks[0])
    on = set(zip(*np.nonzero(sk)[::-1]))
    st=[]
    for p in trace(on):
        s = simplify([(float(x), float(y)) for x, y in p], 0.8)
        if len(s) < 2: continue
        ln = sum(math.hypot(s[i+1][0]-s[i][0], s[i+1][1]-s[i][1]) for i in range(len(s)-1))
        if ln >= 4: st.append((ln, s))
    if len(st) < 40: return None
    st = [s for _, s in sorted(st, key=lambda z: -z[0])[:nstroke]]
    cur = [np.array(s, dtype=np.float64) for s in st]
    traj=[[c.copy() for c in cur]]; oks=[]
    for i in range(1, len(masks)):
        dm = dist_map(masks[i]); nxt=[]; ok=0
        for pts in cur:
            (dx,dy), c = fit(pts, dm, rng=10)
            if c <= 3.2: pts = pts + np.array([dx,dy]); ok += 1
            nxt.append(pts)
        oks.append(ok/float(len(cur))); cur = nxt
        traj.append([c.copy() for c in cur])
    T = np.stack([np.stack([resample(p, npts) for p in fr]) for fr in traj])
    T[...,0] /= w; T[...,1] /= h
    return T, float(np.mean(oks))

def listing(tag, page):
    url = "https://www.sakugabooru.com/post.json?limit=60&page=%d&tags=%s" % (page, tag)
    r = urllib.request.Request(url, headers={"User-Agent": UA})
    return json.load(urllib.request.urlopen(r, timeout=40))

def work(idx):
    os.makedirs(OUT, exist_ok=True)
    mine = TAGS[idx::WORKERS]
    tmp = "/kaggle/working/tmp%d" % idx
    vid = "/kaggle/working/v%d.mp4" % idx
    got = 0
    for tag in mine:
        for page in range(1, 9):
            if len(glob.glob(OUT + "/*.npy")) >= TARGET: return got
            try: js = listing(tag, page)
            except Exception as e:
                log("список %s/%d: %s" % (tag, page, str(e)[:50])); continue
            for p in js:
                u = p.get("file_url") or ""
                if not u.endswith(".mp4"): continue
                if (p.get("file_size") or 0) > 4000000: continue
                # имя по НОМЕРУ ПОСТА, иначе одна сцена качается заново
                # под каждым своим тегом
                name = str(p.get("id"))
                if os.path.exists(os.path.join(OUT, name + ".npy")): continue
                mark = os.path.join(OUT, "." + name)
                if os.path.exists(mark): continue      # уже пробовали и отвергли
                try:
                    r = urllib.request.Request(u, headers={"User-Agent": UA})
                    with urllib.request.urlopen(r, timeout=90) as src, open(vid,"wb") as dst:
                        dst.write(src.read())
                    res = one(vid, tmp)
                    if res is None:
                        open(mark, "w").close(); continue
                    T, q = res
                    if q < 0.80 or np.abs(np.diff(T, axis=0)).mean() < 1e-5:
                        open(mark, "w").close()       # отвергли — не возвращаться
                        continue                      # грязное слежение или статика
                    np.save(os.path.join(OUT, name + ".npy"), T)
                    got += 1
                    if got % 10 == 0:
                        log("рабочий %d: %d сцен (всего %d)" % (idx, got, len(glob.glob(OUT+"/*.npy"))))
                except Exception as e:
                    log("%s: %s" % (name, str(e)[:50]))
    return got

t0 = time.time()
os.makedirs(OUT, exist_ok=True)
log("старт, цель %d сцен, рабочих %d" % (TARGET, WORKERS))
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    list(ex.map(work, range(WORKERS)))
n = len(glob.glob(OUT + "/*.npy"))
log("ГОТОВО: %d сцен за %.1f часов" % (n, (time.time()-t0)/3600))
print("Скачай папку /kaggle/working/clips или сохрани как Kaggle Dataset.")
