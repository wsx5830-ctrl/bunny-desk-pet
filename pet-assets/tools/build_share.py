# -*- coding: utf-8 -*-
"""把桌宠打包成一个可直接发给朋友的 zip（解压即用，无需安装任何运行时）。

用法：python tools/build_share.py
产物：<包根目录>/桌宠-分享包/<名称>/  以及同目录的 <名称>.zip
"""
import os
import shutil
import zipfile
import io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # pet-assets
OUT_ROOT = os.path.join(ROOT, "dist")
PKG_NAME = "兔耳小人桌宠"

README = """兔耳小人 · 桌面桌宠
=====================================

这是一个会待在你屏幕右下角的小家伙：会呼吸、会眨眼、会自己嘀咕话，
被你戳会叫、被你拖会飘、松手会摔下来喊"哎哟"。

【环境要求】
Windows 10 / 11，不需要安装任何软件（用的是系统自带的 PowerShell）。

【怎么启动】
1. 把整个文件夹解压到一个固定位置，比如 D:\\桌宠
   （别放在下载文件夹里，容易被清理工具删掉）
2. 双击 "启动桌宠.vbs"
3. 如果弹出 "Windows 已保护你的电脑"：
   点 "更多信息" → "仍要运行"
   如果杀毒软件提示，选择 "允许"（它只是个本地脚本，不联网）

【怎么玩】
· 点一下它      → Q 弹 + 说话
· 按住拖动      → 会被拎起来，松手自由落体摔到任务栏上
· 右键点它      → 换皮肤（10 套造型 + 主皮肤，会记住你的选择）
· 放着不管      → 会自己嘀咕、会眨眼，90 秒后会睡着，点一下叫醒
· 托盘小图标    → 换皮肤 / 开机自启 / 退出

【想关掉它】
右键点屏幕右下角的托盘小图标 → "退出"

【想开机自动出现】
右键托盘小图标 → 勾选 "开机自启"
（会在启动文件夹里放一个快捷方式，随时可以在同一菜单取消）

【注意】
· 一定要整个文件夹一起用，不要只拷 vbs 文件 —— 皮肤图片在 skins 文件夹里
· 第一次启动会自动在你桌面放一个 "桌宠" 图标，以后双击它就行
· 觉得太大/太小、话说太多/太少，告诉做这个的朋友，一行就能改
"""

TOP_VBS = (
    "' Launch the desktop pet without a console window\r\n"
    "\r\n"
    'Set fso = CreateObject("Scripting.FileSystemObject")\r\n'
    "dir = fso.GetParentFolderName(WScript.ScriptFullName)\r\n"
    'Set sh = CreateObject("WScript.Shell")\r\n'
    "sh.CurrentDirectory = dir\r\n"
    'sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ '
    '& dir & "\\deskpet\\DeskPet.ps1""", 0, False\r\n'
)


def build():
    pkg = os.path.join(OUT_ROOT, PKG_NAME)
    if os.path.isdir(pkg):
        shutil.rmtree(pkg)
    os.makedirs(pkg)

    # deskpet：只带运行必需文件
    dst = os.path.join(pkg, "deskpet")
    os.makedirs(dst)
    for name in ("DeskPet.ps1", "启动桌宠.vbs", "pet.ico"):
        shutil.copy2(os.path.join(ROOT, "deskpet", name), os.path.join(dst, name))

    # 皮肤
    shutil.copytree(os.path.join(ROOT, "skins"), os.path.join(pkg, "skins"),
                    ignore=shutil.ignore_patterns("_*", "*.pyc", "__pycache__"))

    # 台词表
    shutil.copy2(os.path.join(ROOT, "台词表.csv"), os.path.join(pkg, "台词表.csv"))

    # 顶层启动器 + 说明
    with io.open(os.path.join(pkg, "启动桌宠.vbs"), "w", encoding="ascii", newline="") as f:
        f.write(TOP_VBS)
    with io.open(os.path.join(pkg, "使用说明.txt"), "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(README)

    # 预览图（让朋友解压前就知道长什么样）
    prev = os.path.join(ROOT, "skins", "_overview.png")
    if os.path.isfile(prev):
        shutil.copy2(prev, os.path.join(pkg, "预览-11套皮肤.png"))

    # 打包
    zip_path = os.path.join(OUT_ROOT, PKG_NAME + ".zip")
    if os.path.isfile(zip_path):
        os.remove(zip_path)
    n = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for base, dirs, files in os.walk(pkg):
            dirs.sort()
            for fn in sorted(files):
                full = os.path.join(base, fn)
                rel = os.path.relpath(full, OUT_ROOT)
                z.write(full, rel)
                n += 1
    size = os.path.getsize(zip_path) / 1024 / 1024
    print("files:", n)
    print("zip:", zip_path, "%.2f MB" % size)
    return zip_path


if __name__ == "__main__":
    build()
