# 配图路由：什么时候画、画什么、怎么画

精读笔记的图不是装饰，是**论证的一部分**。只画两种，最多三张。

| 图 | 回答什么问题 | 用什么 | 输出 |
| --- | --- | --- | --- |
| **方法流程图** | 关键新想法是怎么组织的？数据/梯度怎么流动？ | `textbook-svg` Track A（纯 SVG） | `fig/method.svg` |
| **主张-证据图** | 主方法相对基线到底强多少？消融去掉某组件掉多少？ | `figures4papers` 规范 + `scripts/paper_style.py` | `fig/evidence.svg` + `.png` |
| （可选）**失败/边界示意** | 在什么条件下失效？ | `textbook-svg` Track A（contrast 对比型） | `fig/limit.svg` |

**不画**：论文原图截图（版权 + 无增量）、装饰性架构堆叠图、从摘要抄来的"贡献三点图"。

---

## 一、方法流程图（textbook-svg）

Track A 是 700–760px 的原生 SVG，零外部依赖，插进 md 后字号不会被缩成蚂蚁字。

### 标准动作

```bash
SKILL_SVG=~/.workbuddy/skills/textbook-svg/scripts/svg_tool.py

# 1) 选一个最贴近的构图母版：pillars（三支柱）/ matrix（四象限）
#    / branch（条件分支）/ contrast（正反对比）
uv run "$SKILL_SVG" scaffold --archetype branch --output fig/method.svg

# 2) 打开 fig/method.svg，把所有占位文字换成论文里的真实术语
#    （保留 rect/line/marker 的坐标与配色，只改 <text> 内容和卡片宽度）

# 3) 门禁：文字超框、乱码、字号过小都会被拦
uv run "$SKILL_SVG" lint fig/ --output /tmp/svg_lint.json
```

`lint` 报 `all_valid: false` 就不要交付——通常是某个 `<text>` 比它的 `<rect>` 宽，缩短措辞或加宽卡片。

### 内容要求

- 节点文字用**论文的术语**（`γ, β`、`mini-batch mean`、`internal covariate shift`），不要写"模块一/模块二"。
- 每条边标出**张量形状或数据含义**（如 `x: [N,C,H,W]`），这才叫信息量。
- 必须能回答一个问题：「如果我是作者，我会先看哪一块？」——那块应该是视觉重心。

---

## 二、主张-证据图（figures4papers 规范）

用来替代"把论文主表抄一遍"。要求：**数据全部来自论文原表/原图**，并在图注里写明出处。

```python
import sys
sys.path.insert(0, r"C:/Users/86139/.workbuddy/skills/paper-deep-reading/scripts")
from paper_style import setup, style_axes, save, annotate_values, OURS, BASES, RED
import numpy as np
from matplotlib import pyplot as plt

setup(wide=True)          # 16x5 超宽画布 + 中文字体 + 学术字号

methods = ["Inception", "BN-Baseline", "BN-x5", "BN-x30", "BN-x5-Sigmoid"]
steps   = [31.0, 13.3, 2.1, 2.7, None]      # 单位：10^6 步，None=未达标
colors  = [BASES[0], BASES[1], OURS, OURS, RED]

fig, ax = plt.subplots()
bars = ax.bar(methods, [s if s else 0 for s in steps], color=colors,
              edgecolor="white", linewidth=1.2, width=0.62)
style_axes(ax, grid_axis="y")
ax.set_ylabel("训练步数 (×10⁶)")
ax.set_title("达到 Inception 72.2% 精度所需步数（数据来源：原文 Figure 3）", pad=12)
annotate_values(ax, bars, fmt="{:.1f}")
ax.text(4, 1.2, "未达标\n(69.8%)", ha="center", va="bottom", fontsize=11, color=RED)
plt.xticks(rotation=12, ha="right")
save(fig, "fig/evidence.svg")
```

### 硬性要求

1. **每条数据在图注里标出处**：`数据来源：原文 Table 3 / Figure 3`。抄错比不画更糟。
2. 主方法用 `OURS` 深蓝，基线用 `BASES` 红系——读者 3 秒内能定位"谁是新方法"。
3. 柱顶标数值（`annotate_values`），不要让人去对 Y 轴。
4. 一张图只服务一个主张。主张多了拆图。
5. 缺数据就**留白并标注**（如上例的"未达标"），不要用 0 冒充。

---

## 三、嵌入笔记

```markdown
![方法总览：BN 插入位置与训练/推理差异](fig/method.svg)

![达到同等精度所需训练步数](fig/evidence.svg)
```

- 路径用**相对 `note.md` 的相对路径**，归档进 Zotero 后 linked attachment 仍能打开。
- 同时保留 `.png`：部分渲染器（含 Zotero 笔记内的图片预览）对 SVG 支持不稳定。
- 图注写"结论"，不要写"XX 图"。

---

## 四、交付前门禁

- [ ] `lint` 通过（0 error）
- [ ] 图里每个数字都能在原文找到
- [ ] 图注写明了数据出处
- [ ] 节点/坐标轴用的是论文术语而非自造词
- [ ] 图片宽度 ≤ 1000px（避免插入 md 后被整体缩放导致字号过小）
