#!/usr/bin/env python3
"""
Фигура на скелете. Поза задаётся углами, а не координатами — поэтому
её можно поворачивать, и конечности ходят по дугам сами собой.
Рисуется не палками: у каждой кости есть толщина и сужение.
"""
import math, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import strokes as S

def pol(p, ang, ln):
    return (p[0] + ln * math.cos(ang), p[1] + ln * math.sin(ang))

def taper(a, b, w0, w1, bend=0.0, n=7):
    """кость с сужением и лёгким изгибом"""
    ax, ay = a; bx, by = b
    nx, ny = -(by - ay), (bx - ax)
    L = math.hypot(nx, ny) or 1.0
    nx, ny = nx / L, ny / L
    pts = []
    for i in range(n):
        t = i / (n - 1.0)
        k = math.sin(math.pi * t) * bend
        pts.append([ax + (bx - ax) * t + nx * k, ay + (by - ay) * t + ny * k, w0 + (w1 - w0) * t])
    return pts

def oval(c, rx, ry, rot=0.0, n=20):
    out = []
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        out.append([c[0] + x * math.cos(rot) - y * math.sin(rot),
                    c[1] + x * math.sin(rot) + y * math.cos(rot), 2.0])
    return out

# Все углы АБСОЛЮТНЫЕ, в экранных координатах: y растёт вниз,
# поэтому pi/2 это строго вниз, -pi/2 строго вверх.
DEF = dict(hipx=0.50, hipy=0.54, spine=-math.pi/2, spine_len=0.150,
           head_tilt=0.0,
           armL=1.15, foreL=1.35, armR=1.99, foreR=1.79,
           thighL=1.40, shinL=1.52, thighR=1.74, shinR=1.62,
           squash=1.0, scale=1.9)

def skeleton(p):
    hip = (p["hipx"], p["hipy"])
    sc = p["scale"]
    neck = pol(hip, p["spine"], p["spine_len"] * sc * p["squash"] * 0.5)
    head = pol(neck, p["spine"] + p["head_tilt"], 0.062 * sc * p["squash"])
    shoL = pol(neck, 0.0, 0.040 * sc)
    shoR = pol(neck, math.pi, 0.040 * sc)
    elbL = pol(shoL, p["armL"], 0.080 * sc)
    hndL = pol(elbL, p["foreL"], 0.076 * sc)
    elbR = pol(shoR, p["armR"], 0.080 * sc)
    hndR = pol(elbR, p["foreR"], 0.076 * sc)
    hipL = pol(hip, 0.0, 0.028 * sc)
    hipR = pol(hip, math.pi, 0.028 * sc)
    kneL = pol(hipL, p["thighL"], 0.095 * sc)
    ftL  = pol(kneL, p["shinL"], 0.092 * sc)
    kneR = pol(hipR, p["thighR"], 0.095 * sc)
    ftR  = pol(kneR, p["shinR"], 0.092 * sc)
    return dict(hip=hip, neck=neck, head=head, shoL=shoL, shoR=shoR,
                elbL=elbL, hndL=hndL, elbR=elbR, hndR=hndR,
                hipL=hipL, hipR=hipR, kneL=kneL, ftL=ftL, kneR=kneR, ftR=ftR)

def draw(p, hair_lag=(0, 0), coat_lag=(0, 0), smear=None):
    j = skeleton(p)
    sc = p["scale"]
    st = []
    hd = j["head"]
    # голова и лицо
    st.append({"id": 1, "w": 2.4, "pts": oval(hd, 0.044*sc, 0.052*sc*p["squash"], p["spine"]+math.pi/2+p["head_tilt"])})
    ex = 0.016*sc
    st.append({"id": 2, "w": 2.0, "pts": [[hd[0]-ex, hd[1]-0.004, 2.0], [hd[0]-ex*0.3, hd[1]-0.010, 2.4], [hd[0]+ex*0.1, hd[1]-0.004, 2.0]]})
    st.append({"id": 3, "w": 2.0, "pts": [[hd[0]+ex*0.5, hd[1]-0.004, 2.0], [hd[0]+ex*1.1, hd[1]-0.010, 2.4], [hd[0]+ex*1.7, hd[1]-0.004, 2.0]]})
    st.append({"id": 4, "w": 2.2, "pts": [[hd[0]-ex*0.4, hd[1]+0.022, 2.2], [hd[0]+ex*0.3, hd[1]+0.027, 2.6], [hd[0]+ex*1.0, hd[1]+0.022, 2.2]]})
    # волосы: пряди отстают от движения
    hx, hy = hair_lag
    # пряди начинаются на макушке и падают вниз, отставая от движения
    for k, (sx, ex, bend) in enumerate([(-0.046, -0.060, -0.04), (-0.018, -0.030, -0.02),
                                        (0.018, 0.030, 0.02), (0.046, 0.060, 0.04)]):
        root = (hd[0] + sx*sc, hd[1] - 0.040*sc)
        tip  = (hd[0] + ex*sc*2.6 - hx*2.4, hd[1] + 0.070*sc - hy*2.4)
        st.append({"id": 10+k, "w": 2.2, "pts": taper(root, tip, 2.8, 1.2, bend)})
    # корпус: два контура, а не одна палка
    st.append({"id": 20, "w": 3.0, "pts": taper(j["shoL"], j["hipL"], 3.0, 2.4, 0.012)})
    st.append({"id": 21, "w": 3.0, "pts": taper(j["shoR"], j["hipR"], 3.0, 2.4, -0.012)})
    st.append({"id": 22, "w": 2.4, "pts": taper(j["shoL"], j["shoR"], 2.4, 2.4, 0.010)})
    st.append({"id": 23, "w": 2.4, "pts": taper(j["hipL"], j["hipR"], 2.4, 2.4, -0.006)})
    # плащ: подол отстаёт
    cx, cy = coat_lag
    st.append({"id": 30, "w": 2.6, "pts": taper(j["shoL"], (j["hipL"][0]+0.070*sc-cx*2.5, j["hipL"][1]+0.120*sc-cy*2.0), 2.8, 1.4, 0.035)})
    st.append({"id": 31, "w": 2.6, "pts": taper(j["shoR"], (j["hipR"][0]-0.070*sc-cx*2.5, j["hipR"][1]+0.120*sc-cy*2.0), 2.8, 1.4, -0.035)})
    # руки
    if smear:
        a, b = smear
        st.append({"id": 40, "w": 6.0, "pts": [[a[0], a[1], 5.5], [(a[0]+b[0])/2, (a[1]+b[1])/2 - 0.008, 4.0], [b[0], b[1], 2.5]]})
        st.append({"id": 41, "w": 3.0, "pts": [[a[0], a[1]+0.018, 3.0], [b[0], b[1]+0.012, 1.5]]})
    else:
        st.append({"id": 40, "w": 2.8, "pts": taper(j["shoR"], j["elbR"], 3.0, 2.6, 0.015)})
        st.append({"id": 41, "w": 2.6, "pts": taper(j["elbR"], j["hndR"], 2.6, 2.2, 0.012)})
        st.append({"id": 42, "w": 2.4, "pts": oval(j["hndR"], 0.020*sc, 0.017*sc)})
    st.append({"id": 43, "w": 2.8, "pts": taper(j["shoL"], j["elbL"], 3.0, 2.6, -0.015)})
    st.append({"id": 44, "w": 2.6, "pts": taper(j["elbL"], j["hndL"], 2.6, 2.2, -0.012)})
    st.append({"id": 45, "w": 2.4, "pts": oval(j["hndL"], 0.019*sc, 0.016*sc)})
    # ноги
    st.append({"id": 50, "w": 3.2, "pts": taper(j["hipL"], j["kneL"], 3.4, 2.8, -0.012)})
    st.append({"id": 51, "w": 2.8, "pts": taper(j["kneL"], j["ftL"], 2.8, 2.2, -0.010)})
    st.append({"id": 52, "w": 2.6, "pts": taper(j["ftL"], (j["ftL"][0]+0.034*sc, j["ftL"][1]+0.006), 2.6, 2.0)})
    st.append({"id": 53, "w": 3.2, "pts": taper(j["hipR"], j["kneR"], 3.4, 2.8, 0.012)})
    st.append({"id": 54, "w": 2.8, "pts": taper(j["kneR"], j["ftR"], 2.8, 2.2, 0.010)})
    st.append({"id": 55, "w": 2.6, "pts": taper(j["ftR"], (j["ftR"][0]-0.034*sc, j["ftR"][1]+0.006), 2.6, 2.0)})
    return {"strokes": st}, j
