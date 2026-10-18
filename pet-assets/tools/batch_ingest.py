"""批量接入十套皮肤。男宝2 需先剥掉贴纸白边（透明贴纸图的白描边会被当成部件）。"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest_skin import ingest, cut_bg  # noqa: E402

DESK = r"C:/Users/XIAOMI/Desktop"
TMP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skins", "_tmp_src")
os.makedirs(TMP, exist_ok=True)

# 男宝2：透明贴纸带白边 -> flatten 白底后按白底抠（从边缘 flood fill 吃掉贴纸白边）
flat = os.path.join(TMP, "nanbao2_flat.png")


def _prep_nanbao2():
    pre = os.path.join(TMP, "nanbao2_pre.png")
    if not os.path.exists(pre):
        im = Image.open(os.path.join(DESK, "男宝2.PNG")).convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        bg.convert("RGB").save(pre)
    cut = cut_bg(pre)              # flood fill 从边缘吃掉白色贴纸边
    cut.save(flat)
    print("nanbao2 sticker edge stripped:", cut.size)


_prep_nanbao2()

JOBS = [
    ("一公.PNG",     "yigong",   "一公 · 红外套火焰", "#C23B3B"),
    ("常服1.JPG",    "casual1",  "常服 · 蓝贝雷帽",   "#5B7E9E"),
    ("二公.PNG",     "ergong",   "二公 · 格纹马甲",   "#4A6FA5"),
    ("常服2.JPG",    "casual2",  "常服 · 红毛衣比心", "#C0392B"),
    ("男宝2.PNG",    "nanbao2",  "西装猪猪",         "#7C93B5"),
    ("常服3.JPG",    "casual3",  "常服 · 棒球帽夹克", "#3A3F4A"),
    ("翰林校服.JPG",  "hanlin",   "翰林校服",         "#2C3A5C"),
    ("常服4.JPG",    "casual4",  "常服 · 藏蓝外套",   "#3E517A"),
    ("常服5.JPG",    "sitting",  "常服 · 坐坐",      "#8A6748"),
    ("常服6.JPG",    "casual6",  "常服 · 蓝帽背带裤", "#7FA8D9"),
]

for fname, sid, name, accent in JOBS:
    src = flat if fname == "男宝2.PNG" else os.path.join(DESK, fname)
    try:
        meta = ingest(src, sid, name, accent)
        print("OK", sid, "layers:", len(meta["layers"]))
    except Exception:
        import traceback
        print("FAIL", sid, fname)
        traceback.print_exc()
