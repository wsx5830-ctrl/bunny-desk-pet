"""把单张角色图拆成可做骨骼/剪纸动画的分层 PNG（v4）。

部件都有黑描边：先按亮度分“墨线/留白”，留白按连通域分块，
中间调像素最后按最近区域归属；墨线按下巴线切头发/衣服；
眼睛用腐蚀核心从脸内找出（眼与刘海描边连通时仍可分离）。
"""
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage

MASTER = r"C:\Users\XIAOMI\WorkBuddy\2026-10-18-14-45-54\pet-assets\character\cut_master.png"
OUTDIR = r"C:\Users\XIAOMI\WorkBuddy\2026-10-18-14-45-54\pet-assets\character\layers"

im = Image.open(MASTER).convert("RGBA")
rgb = np.array(im)
a = rgb.astype(np.int16)
r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
h, w = r.shape
solid = al > 40

v = np.maximum(np.maximum(r, g), b)
dark = solid & (v < 150)
pale = solid & (v >= 170)
pink = (r - g > 55) & (r > 190) & solid

clab = ndimage.label(pale)[0]
n = clab.max()
objs = ndimage.find_objects(clab)
sizes = ndimage.sum_labels(np.ones_like(clab), clab, range(1, n + 1))
cstat = []
for i in range(1, n + 1):
    if sizes[i - 1] < 200:
        continue
    ys, xs = objs[i - 1]
    mean = rgb[clab == i][:, :3].mean(axis=0)
    cstat.append(dict(id=i, size=int(sizes[i - 1]), mean=mean,
                      pale=bool(mean.min() > 190), y0=ys.start, y1=ys.stop,
                      x0=xs.start, x1=xs.stop,
                      cy=(ys.start + ys.stop) / 2, cx=(xs.start + xs.stop) / 2))

center = np.array([w / 2, h * 0.55])
face = min([s for s in cstat if s["size"] > 5000],
           key=lambda s: np.hypot(s["cx"] - center[0], s["cy"] - center[1]))
chin = face["y1"]
fcx = (face["x0"] + face["x1"]) / 2
fh = face["y1"] - face["y0"]
print("face:", face["size"], "chin:", chin, "fcx:", fcx)

shorts = max([s for s in cstat if s["cy"] > chin + 40 and s["size"] > 1500],
             key=lambda s: s["size"], default=None)

# 手：下巴附近两侧的浅色块，按左右合并（手指和手掌可能是分开的连通域）
hand_comps = [s for s in cstat if s["size"] > 400 and s["cy"] > chin - 110
              and s["cy"] < chin + 280 and abs(s["cx"] - fcx) > 70]
hand_comps.sort(key=lambda s: s["cx"])
hand_L = [s for s in hand_comps if s["cx"] < fcx]
hand_R = [s for s in hand_comps if s["cx"] >= fcx]
print("hand comps L/R:", [(s["size"], int(s["cx"]), int(s["cy"])) for s in hand_L],
      [(s["size"], int(s["cx"]), int(s["cy"])) for s in hand_R])

dlab = ndimage.label(dark)[0]
dn = dlab.max()
dobjs = ndimage.find_objects(dlab)
dsizes = ndimage.sum_labels(np.ones_like(dlab), dlab, range(1, dn + 1))
dstat = []
for i in range(1, dn + 1):
    if dsizes[i - 1] < 100:
        continue
    ys, xs = dobjs[i - 1]
    dstat.append(dict(id=i, size=int(dsizes[i - 1]), y0=ys.start, y1=ys.stop,
                      x0=xs.start, x1=xs.stop,
                      cy=(ys.start + ys.stop) / 2, cx=(xs.start + xs.stop) / 2))
ink = max(dstat, key=lambda s: s["size"])

# 眼睛：脸内独立的暗块；找不到就用腐蚀核心（眼与刘海描边连通的情况）
eyes = [s for s in dstat if s["id"] != ink["id"] and s["size"] > 300
        and s["x0"] >= face["x0"] - 5 and s["x1"] <= face["x1"] + 5
        and s["y0"] >= face["y0"] - 5 and s["y1"] <= chin + 5]
if len(eyes) < 2:
    for it in (8, 11, 14):
        core = ndimage.binary_erosion(dark, iterations=it)
        corelab = ndimage.label(core)[0]
        cn = corelab.max()
        cobjs = ndimage.find_objects(corelab)
        csizes = ndimage.sum_labels(np.ones_like(corelab), corelab, range(1, cn + 1))
        ecands = []
        for i in range(1, cn + 1):
            if csizes[i - 1] < 120:
                continue
            ys, xs = cobjs[i - 1]
            if xs.start >= face["x0"] - 5 and xs.stop <= face["x1"] + 5 \
               and ys.start >= face["y0"] - 5 and ys.stop <= chin + 5:
                ecands.append(dict(id=i, size=int(csizes[i - 1]), y0=ys.start, y1=ys.stop,
                                   x0=xs.start, x1=xs.stop,
                                   cy=(ys.start + ys.stop) / 2, cx=(xs.start + xs.stop) / 2))
        ecands.sort(key=lambda s: s["cx"])
        if len(ecands) >= 2:
            break
    eyes = ecands[:2]
    eye_from_core = True
else:
    eye_from_core = False
print("eyes:", [(s["size"], int(s["cx"]), int(s["cy"])) for s in eyes], "from_core:", eye_from_core)

# ---------- 组装（顺序即层级，后写的覆盖先写的） ----------
lab = np.zeros((h, w), np.int32)
names = {}
nid = 0


def put(mask, name):
    global nid
    nid += 1
    lab[mask] = nid
    names[nid] = name


yy = np.arange(h)[:, None]
xx = np.arange(w)[None, :]

put(clab == face["id"], "face")

# 嘴：脸下半部、水平居中的粉色
mm = np.zeros((h, w), bool)
mm[face["y0"] + int(fh * 0.3):chin - 5, max(0, int(fcx - 90)):int(fcx + 90)] = True
put(mm & pink, "mouth")

# 手（左右各自合并多个连通域 + 粉色 X）
for side, comps in (("hand_L", hand_L), ("hand_R", hand_R)):
    if not comps:
        continue
    m = np.zeros((h, w), bool)
    for s in comps:
        m |= clab == s["id"]
    for s in comps:  # 邻域内的粉色 X
        sl = (slice(max(0, s["y0"] - 30), min(h, s["y1"] + 30)),
              slice(max(0, s["x0"] - 30), min(w, s["x1"] + 30)))
        m[sl] |= pink[sl]
    put(m, side)

if shorts:
    put(clab == shorts["id"], "shorts")

# 耳朵：下巴线以上、脸/手以外的浅色（要求有暖调，排除灰色投影边），按中线分左右
ear_zone = pale & (yy < chin) & (clab != face["id"]) & ((r - b) >= 6)
for s in hand_L + hand_R:
    ear_zone[max(0, s["y0"] - 30):s["y1"] + 30, max(0, s["x0"] - 30):s["x1"] + 30] = False
put(ear_zone & (xx < fcx), "ear_L")
put(ear_zone & (xx >= fcx), "ear_R")

ink_mask = dlab == ink["id"]
put(ink_mask & (yy <= chin), "hair")
put(ink_mask & (yy > chin), "body")

# 眼睛（最后写，从头发里抠出来）
for i, s in enumerate(eyes):
    name = "eye_L" if i == 0 else "eye_R"
    if eye_from_core:
        box = (slice(max(0, s["y0"] - 12), s["y1"] + 12), slice(max(0, s["x0"] - 12), s["x1"] + 12))
        region = np.zeros((h, w), bool)
        region[box] = True
        corem = corelab == s["id"]
        m = region & dark & ndimage.binary_dilation(corem, iterations=10)
    else:
        m = dlab == s["id"]
    put(m, name)
    # 眼白高光
    if eye_from_core:
        hl_zone = np.zeros((h, w), bool)
        hl_zone[s["y0"]:s["y1"], s["x0"]:s["x1"]] = True
        for c in cstat:
            if c["pale"] and c["size"] < 2500 \
               and c["x0"] >= s["x0"] and c["x1"] <= s["x1"] \
               and c["y0"] >= s["y0"] and c["y1"] <= s["y1"]:
                put(clab == c["id"], name)
    else:
        for c in cstat:
            if c["pale"] and c["size"] < 2500 \
               and c["x0"] >= s["x0"] and c["x1"] <= s["x1"] \
               and c["y0"] >= s["y0"] and c["y1"] <= s["y1"]:
                put(clab == c["id"], name)

# —— 杂散暗块归还：耳朵与发带之间的阴影楔形是头发，不该跟着耳朵转 ——
name_of = {}
nidx = {}
for lid, nm in names.items():
    name_of[lid] = nm
    if nm not in nidx:
        nidx[nm] = len(nidx) + 1
nl = np.zeros((h, w), np.int32)
for lid, nm in names.items():
    nl[lab == lid] = nidx[nm]

ear_pale = pale & ((nl == nidx["ear_L"]) | (nl == nidx["ear_R"]))
d_earpale = ndimage.distance_transform_edt(~ear_pale)
fb = np.zeros((h, w), bool)
fb[max(0, face["y0"]):chin + 5, max(0, face["x0"] - 5):min(w, face["x1"] + 5)] = True
rem = solid & (lab == 0) & dark
deep = rem & (d_earpale > 8)   # 距耳朵浅色区 8px 以上的深色像素不可能是耳朵描边
put(deep & ~fb & (yy <= chin), "hair")
put(deep & ~fb & (yy > chin), "body")
put(deep & fb, "face")

unlabeled = int((solid & (lab == 0)).sum())
print("unlabeled:", unlabeled)

# 灰色投影边（低饱和、无暖调的中间调）不属于任何部件：整块丢弃，保持透明
was_unlabeled = solid & (lab == 0)
grayish = was_unlabeled & (v >= 150) & ((r - b) < 8) \
    & ((np.maximum(r, g, b) - np.minimum(r, g, b)) < 30)
print("gray shadow px dropped:", int(grayish.sum()))

_, (iy, ix) = ndimage.distance_transform_edt(lab == 0, return_indices=True)
lab[solid] = lab[iy[solid], ix[solid]]
lab[grayish] = 0

os.makedirs(OUTDIR, exist_ok=True)

# 同名多段合并；出血改为“向内取色”：边缘外扩的像素复制本层最近的内部颜色，
# 而不是邻居层的像素，旋转时就不会拖出深色边
by_name = {}
for lid, name in names.items():
    by_name.setdefault(name, np.zeros((h, w), bool))[lab == lid] = True

out = []
for name, m in by_name.items():
    if m.sum() < 30:
        continue
    dil = ndimage.binary_dilation(m, iterations=3)
    fringe = dil & ~m
    _, (fys, fxs) = ndimage.distance_transform_edt(~m, return_indices=True)
    rgba = rgb.copy()
    rgba[..., 3] = np.where(dil, 255, 0).astype(np.uint8)
    rgba[~dil] = 0
    for ch in range(3):
        rgba[fringe, ch] = rgb[fys[fringe], fxs[fringe], ch]
    # 轻微羽化 alpha，旋转时边缘平滑不出锯齿
    rgba[..., 3] = ndimage.gaussian_filter(rgba[..., 3].astype(np.float32), 0.7).clip(0, 255).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(os.path.join(OUTDIR, name + ".png"))
    ys, xs = np.nonzero(m)
    out.append(dict(name=name, size=int(m.sum()),
                    box=[int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]))

boxes = {o["name"]: o["box"] for o in out}
pivots = {}
head_top = np.array([fcx, face["y0"]])
for e in ("ear_L", "ear_R"):
    if e in boxes:
        ys, xs = np.nonzero(by_name[e])
        d2 = (xs - head_top[0]) ** 2 + (ys - head_top[1]) ** 2
        j = int(np.argmin(d2))
        pivots[e] = [int(xs[j]), int(ys[j])]
for nm in ("face", "hair"):
    if nm in boxes:
        pivots[nm] = [int(fcx), int(chin) - 5]
for e in ("eye_L", "eye_R"):
    if e in boxes:
        x0, y0, x1, y1 = boxes[e]
        pivots[e] = [int((x0 + x1) / 2), int((y0 + y1) / 2)]
if "body" in boxes:
    x0, y0, x1, y1 = boxes["body"]
    pivots["body"] = [int((x0 + x1) / 2), int(y1)]

palette = [(0, 0, 0), (205, 92, 92), (230, 150, 60), (95, 125, 215), (250, 218, 205),
           (60, 180, 160), (155, 95, 200), (225, 90, 160), (115, 115, 115),
           (245, 245, 245), (95, 200, 95), (200, 200, 70), (70, 70, 185), (200, 120, 60)]
dbg = np.full((h, w, 3), 255, np.uint8)
for i, (name, m) in enumerate(by_name.items()):
    dbg[m] = palette[(i + 1) % len(palette)]
Image.fromarray(dbg, "RGB").save(os.path.join(OUTDIR, "_debug_segmentation.png"))

with open(os.path.join(OUTDIR, "layers.json"), "w", encoding="utf-8") as f:
    json.dump({"canvas": [w, h], "layers": out, "pivots": pivots}, f, ensure_ascii=False, indent=1)
print(json.dumps([{ "name": o["name"], "size": o["size"]} for o in out], ensure_ascii=False))
print("pivots:", json.dumps(pivots))
