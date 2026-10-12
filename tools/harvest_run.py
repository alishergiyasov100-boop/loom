#!/usr/bin/env python3
"""Долгий сбор: качает клипы с архива и превращает их в траектории."""
import sys, os, json, time, subprocess, urllib.request, glob
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from harvest import one

UA = "Mozilla/5.0 (Linux; Android 14) PocketCode"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "clips")
LOG = os.path.join(os.path.dirname(__file__), "..", "harvest.log")
TAGS = ["character_acting", "walk_cycle", "fighting", "effects",
        "hair", "fabric", "smears", "running", "dialogue", "creatures",
        "animated", "background_animation", "impact_frames", "debris",
        "food", "sports", "vehicle", "rotation", "morphing", "presumed"]

def log(m):
    with open(LOG, "a") as f:
        f.write("%s  %s\n" % (time.strftime("%H:%M:%S"), m))

def fetch_json(url):
    r = urllib.request.Request(url, headers={"User-Agent": UA})
    return json.load(urllib.request.urlopen(r, timeout=40))

def main(target=200, worker=0, nworkers=1):
    """Каждый рабочий берёт свои теги — пересечений нет, блокировки не нужны."""
    os.makedirs(OUT, exist_ok=True)
    done = {os.path.basename(f)[:-4] for f in glob.glob(os.path.join(OUT, "*.npy"))}
    log("рабочий %d/%d: старт, уже собрано %d" % (worker, nworkers, len(done)))
    got = len(done)
    mine = TAGS[worker::nworkers]
    for tag in mine:
        for page in range(1, 6):
            if got >= target: break
            try:
                js = fetch_json("https://www.sakugabooru.com/post.json?limit=60&page=%d&tags=%s" % (page, tag))
            except Exception as e:
                log("список %s стр %d: %s" % (tag, page, str(e)[:60])); continue
            for p in js:
                if got >= target: break
                u = p.get("file_url") or ""
                if not u.endswith(".mp4"): continue
                if (p.get("file_size") or 0) > 4000000: continue
                name = "%s_%s" % (tag[:6], p.get("id"))
                if name in done: continue
                tmp = "/tmp/hv_%d.mp4" % worker
                try:
                    r = urllib.request.Request(u, headers={"User-Agent": UA})
                    with urllib.request.urlopen(r, timeout=90) as src, open(tmp, "wb") as dst:
                        dst.write(src.read())
                    res = one(tmp)
                    if res is None:
                        log("%s пропуск" % name); continue
                    T, q = res
                    if q < 0.55 or np.abs(np.diff(T, axis=0)).mean() < 1e-5:
                        log("%s плохое слежение %.2f" % (name, q)); continue
                    np.save(os.path.join(OUT, name + ".npy"), T)
                    done.add(name); got += 1
                    log("%s ok %s q=%.2f (всего %d)" % (name, T.shape, q, got))
                except Exception as e:
                    log("%s ошибка %s" % (name, str(e)[:60]))
    log("готово, собрано %d" % got)

if __name__ == "__main__":
    t = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    w = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    main(t, w, n)
