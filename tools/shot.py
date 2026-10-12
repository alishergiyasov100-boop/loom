#!/usr/bin/env python3
"""
Эпизод: замах — удар — попадание — отход.

Всё, о чём мы говорили, применено буквально:
  упреждение   — перед ударом фигура уходит назад
  дуги         — кулак идёт по окружности вокруг плеча, не по прямой
  интервалы    — замах медленный, удар в один-два кадра, отход вязкий
  сжатие       — на удар корпус вытягивается, на попадании сплющивается
  смир         — на самых быстрых кадрах рука рисуется мазком, а не рукой
  отставание   — волосы и плащ идут за телом с опозданием
  тряска       — камера дёргается на попадании
"""
import math, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import strokes as S

def ease_out(t):  return 1 - (1 - t) ** 3
def ease_in(t):   return t * t * t
def ease_both(t): return t * t * (3 - 2 * t)

def lerp(a, b, t): return a + (b - a) * t

def arc(a, b, centre, t):
    """движение по дуге вокруг точки, а не по прямой"""
    ax, ay = a[0] - centre[0], a[1] - centre[1]
    bx, by = b[0] - centre[0], b[1] - centre[1]
    ra, rb = math.hypot(ax, ay), math.hypot(bx, by)
    aa, ab = math.atan2(ay, ax), math.atan2(by, bx)
    d = ab - aa
    while d > math.pi:  d -= 2 * math.pi
    while d < -math.pi: d += 2 * math.pi
    r = lerp(ra, rb, t); ang = aa + d * t
    return (centre[0] + r * math.cos(ang), centre[1] + r * math.sin(ang))

def circle(c, rx, ry, n=18):
    return [(c[0] + rx * math.cos(2*math.pi*i/n), c[1] + ry * math.sin(2*math.pi*i/n)) for i in range(n+1)]

def curve(a, b, bend=0.0, n=7):
    ax, ay = a; bx, by = b
    nx, ny = -(by-ay), (bx-ax)
    L = math.hypot(nx, ny) or 1.0
    nx, ny = nx/L, ny/L
    return [(lerp(ax,bx,i/(n-1.0)) + nx*math.sin(math.pi*i/(n-1.0))*bend,
             lerp(ay,by,i/(n-1.0)) + ny*math.sin(math.pi*i/(n-1.0))*bend) for i in range(n)]

# ---- ключевые позы: (кадр, корпус, плечо, кулак, наклон, сжатие) ----
KEYS = [
    (0,   0.50, 0.42, (0.38, 0.47), 0.00, 1.00),   # стойка
    (10,  0.52, 0.44, (0.30, 0.44), -0.05, 1.00),  # начало замаха
    (22,  0.54, 0.45, (0.24, 0.40), -0.12, 0.96),  # крайний замах, упреждение
    (26,  0.52, 0.44, (0.28, 0.42), -0.08, 1.02),  # сжатие перед броском
    (29,  0.48, 0.42, (0.62, 0.46), 0.10, 1.10),   # УДАР, растяжка
    (31,  0.47, 0.41, (0.70, 0.47), 0.14, 0.88),   # попадание, сплющивание
    (36,  0.49, 0.42, (0.64, 0.47), 0.08, 1.00),   # отдача
    (48,  0.50, 0.42, (0.46, 0.47), 0.02, 1.00),   # возврат
    (62,  0.50, 0.42, (0.38, 0.47), 0.00, 1.00),   # стойка
]
IMPACT = 31
N = 70

def sample(f):
    for i in range(len(KEYS) - 1):
        f0, *_ = KEYS[i]; f1, *_ = KEYS[i+1]
        if f0 <= f <= f1:
            t = 0.0 if f1 == f0 else (f - f0) / float(f1 - f0)
            # интервалы: замах тянется, удар стреляет, отход вязкий
            if f1 <= 22:   e = ease_out(t)
            elif f1 <= 29: e = ease_in(t)
            elif f1 <= 36: e = ease_out(t)
            else:          e = ease_both(t)
            a, b = KEYS[i], KEYS[i+1]
            body = lerp(a[1], b[1], e)
            sho  = lerp(a[2], b[2], e)
            fist = arc(a[3], b[3], (0.48, sho), e) if f1 in (29, 31, 36, 48) else \
                   (lerp(a[3][0], b[3][0], e), lerp(a[3][1], b[3][1], e))
            lean = lerp(a[4], b[4], e)
            sq   = lerp(a[5], b[5], e)
            return body, sho, fist, lean, sq
    return KEYS[-1][1], KEYS[-1][2], KEYS[-1][3], KEYS[-1][4], KEYS[-1][5]

def build():
    frames, hist = [], []
    for f in range(N):
        body, sho, fist, lean, sq = sample(f)
        shake = 0.0
        if IMPACT <= f <= IMPACT + 3:
            shake = 0.012 * (1 - (f - IMPACT) / 4.0) * (1 if f % 2 else -1)
        cx = 0.48 + lean * 0.35 + shake
        hip = (cx, body + 0.16)
        shoulder = (cx + lean * 0.05, sho)
        head = (shoulder[0] + lean * 0.03, shoulder[1] - 0.085 * sq)

        st = []
        st.append(S.stroke(1, circle(head, 0.050, 0.055 * sq), 2.4))
        st.append(S.stroke(2, curve(shoulder, hip, lean * 0.03), 3.0))
        # опорная и толчковая нога
        st.append(S.stroke(3, curve(hip, (hip[0] - 0.09 - lean*0.04, hip[1] + 0.20), -0.02), 2.6))
        st.append(S.stroke(4, curve(hip, (hip[0] + 0.10 + lean*0.06, hip[1] + 0.20), 0.02), 2.6))
        # дальняя рука
        st.append(S.stroke(5, curve(shoulder, (shoulder[0] - 0.10 + lean*0.05, shoulder[1] + 0.14), -0.03), 2.2))
        # бьющая рука: на самых быстрых кадрах — мазок
        prev = hist[-1][2] if hist else fist
        speed = math.hypot(fist[0]-prev[0], fist[1]-prev[1])
        if speed > 0.07:
            st.append(S.stroke(6, [prev, ((prev[0]+fist[0])/2, (prev[1]+fist[1])/2 - 0.01), fist], 5.0))
            st.append(S.stroke(7, [(prev[0], prev[1]+0.02), (fist[0], fist[1]+0.015)], 3.0))
        else:
            st.append(S.stroke(6, curve(shoulder, fist, 0.03 if fist[0] > shoulder[0] else -0.03), 2.6))
            st.append(S.stroke(7, circle(fist, 0.022, 0.022, 10), 2.4))
        # волосы отстают на три кадра
        lag = hist[-3][1] if len(hist) >= 3 else shoulder[0]
        st.append(S.stroke(8, curve((head[0]-0.04, head[1]-0.03),
                                    (head[0]-0.10 + (shoulder[0]-lag)*1.2, head[1]+0.06), -0.04), 2.2))
        st.append(S.stroke(9, curve((head[0]+0.04, head[1]-0.03),
                                    (head[0]+0.09 + (shoulder[0]-lag)*1.2, head[1]+0.05), 0.04), 2.2))
        # попадание: лучи
        if IMPACT <= f <= IMPACT + 2:
            k = (f - IMPACT)
            for i in range(10):
                a = i * math.pi / 5 + k * 0.2
                r0 = 0.03 + k * 0.02; r1 = r0 + 0.05 - k * 0.012
                st.append(S.stroke(100 + i, [(fist[0] + r0*math.cos(a), fist[1] + r0*math.sin(a)),
                                             (fist[0] + r1*math.cos(a), fist[1] + r1*math.sin(a))], 2.6))
        hist.append((head, shoulder[0], fist))
        frames.append({"strokes": st})
    return S.clip(frames, 420, 420, 24, {"shot": "удар"})

if __name__ == "__main__":
    c = build()
    S.save(c, sys.argv[1] if len(sys.argv) > 1 else "data/shot.json")
    print("кадров: %d, длительность %.1f с" % (len(c["frames"]), len(c["frames"]) / 24.0))
