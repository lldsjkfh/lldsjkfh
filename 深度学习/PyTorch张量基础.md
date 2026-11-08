# PyTorch 张量：创建、运算、索引

> 把张量这一层打牢的目标不是「记住 API」，而是**看到形状就知道会发生什么**。这周先把三件事的语义钉死：怎么造、怎么算、怎么取。

## 一、创建：按数据、按固定值、按区间

```python
import torch

torch.tensor([[1, 2], [3, 4]])        # 按数据建，dtype 自动推断
torch.zeros(2, 3)                     # 全 0
torch.ones(2, 3)                      # 全 1
torch.full((2, 3), 7)                 # 全 7（注意形状要写成元组）
torch.eye(3)                          # 单位矩阵

torch.rand(2, 3)                      # [0,1) 均匀
torch.randn(2, 3)                     # 标准正态
torch.randint(0, 10, (2, 3))          # [0,10) 整数
```

### arange 与 linspace：一个不含终点，一个含

```python
torch.arange(0, 10, 2)        # tensor([0, 2, 4, 6, 8])      左闭右开
torch.linspace(0, 10, 5)      # tensor([0., 2.5, 5., 7.5, 10.])   含终点，按个数等分
```

- `arange` 关心**步长**，`linspace` 关心**个数**。
- 用 `arange` 生成浮点序列容易因为累积误差多出/少掉一个元素，需要精确个数时用 `linspace`。

### 类型转换

```python
x.float()      # → float32，喂给模型基本都用这个
x.long()       # → int64，做索引 / 交叉熵标签
x.to(torch.float64)
```

## 二、运算：先分清逐元素还是矩阵乘

```python
x = torch.tensor([[1., 2.], [3., 4.]])
y = torch.tensor([[5., 6.], [7., 8.]])

x * y            # 逐元素乘（Hadamard），不是矩阵乘！
x @ y            # 矩阵乘
torch.mm(x, y)   # 二维矩阵乘，等价于 x @ y
torch.bmm(a, b)  # 三维批量矩阵乘（batch 维不相乘）
```

**这是最容易出错的一处**：`*` 永远是逐元素，矩阵乘必须写 `@`（或 `mm` / `bmm` / `matmul`）。用 `*` 却期待矩阵乘，形状恰好能广播时**不会报错**，只会安静地算错。

### 广播：从最后一维往前比

两条规则，按顺序套：

1. 从**最后一维**往前逐个比；
2. 每一维要么**相等**，要么**其中一个为 1**（为 1 的那一维会被复制扩展），否则报错。

```python
a = torch.zeros(3, 1)
b = torch.zeros(1, 4)
(a + b).shape          # torch.Size([3, 4])   两个 1 各自被扩展

c = torch.zeros(4,)    # 当成 (1, 4)
(a + c).shape          # torch.Size([3, 4])
```

### 聚合：dim 是「要消掉的那一维」

```python
t = torch.arange(12).reshape(3, 4)
t.sum()          # 标量 66
t.sum(dim=0)     # shape (4,)   沿行方向压缩 → 每列求和
t.sum(dim=1)     # shape (3,)   每行求和
t.max(dim=1)     # 返回 (values, indices) 两个张量
t.argmax(dim=1)  # 只返回索引
```

记忆法：**`dim=k` 的意思是「把第 k 维消掉」**，不是「沿着第 k 维遍历」。这也是初学者最容易反的地方。

## 三、索引：切片、布尔、按索引取

```python
t = torch.arange(12).reshape(3, 4)
# tensor([[ 0,  1,  2,  3],
#         [ 4,  5,  6,  7],
#         [ 8,  9, 10, 11]])

t[0:2, 1:3]            # 切片，shape (2, 2)
t[t > 5]               # 布尔筛选 → 一维，tensor([6,7,8,9,10,11])
torch.where(t > 5, t, torch.zeros_like(t))   # 条件选择，形状保持不变
```

### 三个「按索引取」的区别

```python
mask_idx = t > 5
torch.masked_select(t, mask_idx)      # 结果被拍平成一维
t.gather(1, torch.tensor([[0], [3], [1]]))          # 按索引逐位置取值
torch.index_select(t, 1, torch.tensor([0, 2]))      # 按维度整列取，保留维度结构
```

| 方法 | 输出形状 | 用途 |
| --- | --- | --- |
| `masked_select` | 一维（**拍平**） | 只想拿到满足条件的值 |
| `gather` | 与 index 同形 | 每行/每列取**不同**位置的元素（如取最大值的 logits） |
| `index_select` | 保留其余维度 | 按维度挑整行/整列（如挑 batch 中的若干样本） |

`gather` 是最容易看晕的：`gather(dim, index)` 里 `index` 的形状决定输出形状，`index` 里每个数字是**沿 `dim` 方向的下标**，其余维度的坐标取自它自己的位置。

## 四、三个坑

1. **`torch.Tensor(2, 3)` 不是「用 2 和 3 建张量」**，而是「建一个 2×3 的**未初始化**张量」，里面是内存残留的随机值；而 `torch.tensor(2, 3)` 直接报错（`tensor()` 只接一个位置参数）。要建常量张量写 `torch.tensor([2, 3])`。
2. **`arange` 不含终点、`linspace` 含终点**。混着记必然出错。
3. **`dim` 是「要消掉的那一维」**，不是「沿着它遍历的那一维」。`t.sum(dim=1)` 得到的是每行之和（消掉列维），不是每列之和。

## 五、下一步

- [ ] 形状变换：`view` / `reshape` / `permute` / `squeeze` / `unsqueeze`，以及 `view` 为什么要求内存连续
- [ ] 自动微分：`requires_grad`、`backward()`、`.grad`、`detach()` 与 `no_grad()`
- [ ] 用纯张量手写一遍线性回归（前向 + 手算梯度 + 更新），再对比 `nn.Linear` 的写法
