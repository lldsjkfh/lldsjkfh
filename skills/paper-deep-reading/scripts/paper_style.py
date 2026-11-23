#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paper_style.py — 精读笔记配图的统一样式（与 figures4papers 同源规范）

用法：
    import sys; sys.path.insert(0, r"<skill>/scripts")
    from paper_style import setup, OURS, BASES, style_axes, save
    setup()                       # 中文字体 + 学术字号 + 去顶右边框
    ...
    save(fig, "fig/evidence.svg") # 同时落 .svg 与 300dpi .png

设计约束（figures4papers 八条法则的落地）：
  * 主方法用深蓝 #0F4D92，基线用红系渐浅 —— 一眼分出“谁是新方法”
  * 去掉 top/right spine，网格只在 y 轴，浅灰
  * 字号 ≥ 12pt，保证插入 md/PDF 后缩印仍可读
  * 超宽横向画布（3~4:1）承载多指标，避免标签挤压
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# ---- 学术语义色板（figures4papers / textbook-svg 同源）
OURS = "#0F4D92"        # 深蓝：本文方法 / 主模型
OURS_LIGHT = "#6E9BD1"  # 深蓝浅调：本文方法的变体
TEAL = "#2A8C82"        # 青绿：算子 / 增益
RED = "#B64342"         # 深红：最强基线 / 痛点
GOLD = "#D49A35"        # 琥珀：门控 / 折中
GRAY = "#64748B"
BASES = ["#D4685F", "#DA7B73", "#DF8E87", "#E5A19B", "#EBB4AF", "#F1C7C3"]
GRID = "#E2E8F0"

CN_FONTS = ["Microsoft YaHei", "SimHei", "PingFang SC", "Noto Sans CJK SC",
            "Source Han Sans SC", "Hiragino Sans GB"]


def _pick_font():
    have = {f.name for f in font_manager.fontManager.ttflist}
    for name in CN_FONTS:
        if name in have:
            return name
    return None


def setup(font_size=13, title_size=15, wide=False, dpi=300):
    """全局样式。wide=True 时用 3:1 超宽画布（多指标并排）。"""
    cn = _pick_font()
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ([cn] if cn else []) + ["DejaVu Sans"],
        "axes.unicode_minus": False,
        "font.size": font_size,
        "axes.titlesize": title_size,
        "axes.labelsize": font_size,
        "xtick.labelsize": font_size - 1,
        "ytick.labelsize": font_size - 1,
        "legend.fontsize": font_size - 2,
        "axes.edgecolor": "#334155",
        "axes.linewidth": 0.9,
        "figure.dpi": 120,
        "savefig.dpi": dpi,
        "savefig.bbox": "tight",
        "figure.facecolor": "white",
    })
    if wide:
        plt.rcParams["figure.figsize"] = (16, 5)
    return cn


def style_axes(ax, grid_axis="y"):
    """去掉顶/右边框，仅保留浅灰网格。"""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_linewidth(0.9)
        ax.spines[side].set_color("#334155")
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
    ax.tick_params(length=3, width=0.8, colors="#334155")
    return ax


def save(fig, path, also_png=True):
    """同时输出矢量 svg（笔记内嵌）与 300dpi png（兼容性兜底）。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    ext = os.path.splitext(path)[1].lower()
    fig.savefig(path, transparent=False)
    out = [path]
    if also_png and ext == ".svg":
        png = os.path.splitext(path)[0] + ".png"
        fig.savefig(png, dpi=300, transparent=False)
        out.append(png)
    plt.close(fig)
    return out


def annotate_values(ax, bars, fmt="{:.1f}", dy=0.02, fontsize=11, color="#1E293B"):
    """在柱顶标数值：不放纵轴数值刻度也能读，符合定量图规范。"""
    for b in bars:
        h = b.get_height()
        ax.annotate(fmt.format(h), (b.get_x() + b.get_width() / 2, h),
                    textcoords="offset points", xytext=(0, 4),
                    ha="center", va="bottom", fontsize=fontsize, color=color)
