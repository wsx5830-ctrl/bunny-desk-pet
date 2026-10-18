"""扫描 skins/ + 台词表.csv，生成皮肤清单与台词池，注入 pet-demo-skins.html。

台词表.csv 是唯一真源：skin 列留空 = 通用台词（所有皮肤共用），
填皮肤 id = 该皮肤专属台词（权重更高）。改完台词只需重跑本脚本。
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKINS = os.path.join(ROOT, "skins")
CSV = os.path.join(ROOT, "台词表.csv")
HTML = os.path.join(ROOT, "pet-demo-skins.html")

REQUIRED = ["face", "body", "hair"]      # 缺这些层无法成立
# 眼睛至少要有一只；只有一只眼时该皮肤自动 blink=false（单眼眨会穿帮）


def load_quotes():
    """返回 (通用台词池, 每套皮肤的专属台词)。"""
    global_q, per_skin = {}, {}
    if not os.path.isfile(CSV):
        return global_q, per_skin
    with open(CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            skin = (row.get("skin") or "").strip()
            st = (row.get("state") or "").strip()
            text = (row.get("text") or "").strip()
            if not st or not text:
                continue
            target = per_skin.setdefault(skin, {}) if skin else global_q
            target.setdefault(st, []).append(text)
    return global_q, per_skin


def with_anim(meta):
    """补齐动画能力表：未声明时按“有该层就能动”推断，声明的优先。
    安全降级：只有一只眼时强制不眨眼（单眼眨会穿帮）。"""
    roles = [l["role"] for l in meta["layers"]]
    anim = dict(meta.get("anim") or {})
    anim.setdefault("breathe", True)
    anim.setdefault("nod", True)
    anim.setdefault("hairSway", True)
    anim.setdefault("earSway", ("ear_L" in roles or "ear_R" in roles))
    anim.setdefault("tailSway", "tail" in roles)
    if not ("eye_L" in roles and "eye_R" in roles):
        anim["blink"] = False
    else:
        anim.setdefault("blink", True)
    meta["anim"] = anim
    meta["earStatic"] = anim["earSway"] is False
    return meta


def _load_skin(sid, per_skin):
    meta_path = os.path.join(SKINS, sid, "skin.json")
    if not os.path.isfile(meta_path):
        return []
    meta = json.load(open(meta_path, encoding="utf-8"))
    roles = [l["role"] for l in meta["layers"]]
    if not ({"eye_L", "eye_R"} & set(roles)):
        print("SKIP %s: no eye layer at all" % sid)
        return []
    missing = [r for r in REQUIRED if r not in roles]
    for l in meta["layers"]:
        if not os.path.isfile(os.path.join(SKINS, sid, l["src"])):
            print("SKIP %s: missing file %s" % (sid, l["src"]))
            missing.append(l["src"])
    if missing:
        print("SKIP %s: missing %s" % (sid, missing))
        return []

    extra = per_skin.get(sid) or {}
    if extra:
        q = dict(meta.get("quotes") or {})
        for st, arr in extra.items():
            q[st] = list(q.get(st) or []) + arr
        meta["quotes"] = q

    item = with_anim(meta)
    own_n = sum(len(v) for v in item["quotes"].values()) if item.get("quotes") else 0
    print("skin ok:", sid, "-", item["name"],
          "| ears:", "static" if item["earStatic"] else "sway",
          "| blink:", item["anim"]["blink"], "| 专属台词:", own_n)
    return [item]


def collect(per_skin):
    items = []
    for sid in sorted(os.listdir(SKINS)):
        if sid == "default" or not os.path.isdir(os.path.join(SKINS, sid)):
            continue
        items.extend(_load_skin(sid, per_skin))
    return _load_skin("default", per_skin) + items      # 主皮肤永远排第一


def build():
    global_q, per_skin = load_quotes()
    skins = collect(per_skin)
    if not skins:
        sys.exit("no valid skins")

    html = open(HTML, encoding="utf-8").read()
    inj = "//__SKINS_START__\nconst SKINS = %s;\nconst CURRENT_SKIN_ID = %s;\n//__SKINS_END__" % (
        json.dumps(skins, ensure_ascii=False), json.dumps(skins[0]["id"]))
    html, n1 = re.subn(r"//__SKINS_START__.*?//__SKINS_END__", lambda m: inj, html, flags=re.S)

    qinj = "//__QUOTES_START__\nconst QUOTES = %s;\n//__QUOTES_END__" % json.dumps(global_q, ensure_ascii=False)
    html, n2 = re.subn(r"//__QUOTES_START__.*?//__QUOTES_END__", lambda m: qinj, html, flags=re.S)

    if not (n1 and n2):
        sys.exit("marker not found: skins=%d quotes=%d" % (n1, n2))
    open(HTML, "w", encoding="utf-8").write(html)

    total = sum(len(v) for v in global_q.values())
    print("injected %d skins, 通用台词 %d 条（%s）" % (
        len(skins), total, "/".join("%s %d" % (k, len(v)) for k, v in global_q.items())))


if __name__ == "__main__":
    build()
