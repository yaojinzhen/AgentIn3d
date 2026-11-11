# 数学与随机采样

本文档记录单体资产生成中用于固定随机状态、组织随机参数、从常用分布采样、生成稳定 hash 以及处理基础数值的 API。

源码依据：

- `infinigen/core/util/math.py`
- `infinigen/core/util/random.py`

## 推荐导入

```python
import numpy as np

from infinigen.core.util.math import (
    FixedSeed,
    clip_gaussian,
    int_hash,
    lerp,
    normalize,
    randomspacing,
)
from infinigen.core.util.random import (
    log_uniform,
    mixture_of_gaussian,
    random_general,
    weighted_sample,
    wrap_gaussian,
)
```

## `FixedSeed`

签名：

```python
FixedSeed(seed)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `seed` | 可供旧版 `np.random.seed` 使用的整数随机种子 | 优先使用 `factory_seed`、`int_hash((factory_seed, component_name))` 或实例 seed；避免负数和超出 NumPy legacy seed 范围的值 |

行为：

- 进入 context 时保存 Python `random` 和 `numpy.random` 的全局状态。
- 将两个全局随机源都设为指定 seed。
- 退出时恢复进入前状态，即使 context 内抛出异常也会恢复。
- 不控制 Blender 内部随机源，也不控制单独创建的 `np.random.default_rng()`。
- `__enter__` 不返回 RNG object，不要写成 `with FixedSeed(seed) as rng` 后使用 `rng`。

推荐用法：

```python
from infinigen.core.placement.factory import AssetFactory

class CabinetFactory(AssetFactory):
    def __init__(self, factory_seed, coarse=False):
        super().__init__(factory_seed, coarse=coarse)
        with FixedSeed(factory_seed):
            self.width = np.random.uniform(0.7, 1.2)
            self.door_count = np.random.randint(1, 4)
            self.handle_style = weighted_sample(
                [("bar", 0.7), ("knob", 0.3)]
            )
```

推荐在 factory 初始化或明确的参数采样阶段使用 `FixedSeed`，把采样结果保存为字段；不要在不同建模分支中随意增加随机调用，否则同一 seed 后续参数会整体漂移。

## 稳定 Hash

### `int_hash`

签名：

```python
int_hash(x, max=(2**32 - 1)) -> int
```

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `x` | `int`、`str`，或只包含二者的 tuple/list | 组合 seed 时优先使用带分隔符和标签的字符串 |
| `max` | 返回值的模上界 | 保持默认可得到 NumPy seed 范围内的值 |

函数对输入计算 MD5 后取模，适合从一个 seed 派生稳定的子 seed。它不依赖 Python 进程级 hash 随机化，但不是安全加密用途。

tuple/list 中各项会直接按字符串顺序写入 hash，没有自动分隔符；例如纯数字组合可能存在语义不同但拼接结果相同的情况。组件子 seed 优先传入带固定标签的单个字符串。

```python
body_seed = int_hash(f"{factory_seed}:body")
handle_seed = int_hash(f"{factory_seed}:handle")

with FixedSeed(handle_seed):
    handle_radius = np.random.uniform(0.008, 0.015)
```

### `md5_hash`

签名：

```python
md5_hash(x) -> hashlib hash object
```

该函数返回 hash object，而不是十六进制字符串。需要整数 seed 时直接使用 `int_hash`；只有确实需要 `.digest()` 或 `.hexdigest()` 时才使用 `md5_hash`。

## `random_general`

签名：

```python
random_general(var)
```

该函数把 tuple/list 形式的声明式规格解析为一次采样；非 tuple/list 值原样返回。未知操作名也会原样返回输入规格。

| 规格 | 行为 | 备注 |
| --- | --- | --- |
| `("uniform", low, high)` | `np.random.uniform(low, high)` | 连续均匀分布 |
| `("normal", mean, std)` | 正态分布 | 不做截断 |
| `("clip_gaussian", mean, std, low, high)` | 区间内截断正态 | 超过尝试次数后 clip |
| `("log_uniform", low, high)` | 对数均匀分布 | `low`、`high` 必须为正 |
| `("power_uniform", low_exp, high_exp)` | `10 ** U(low_exp, high_exp)` | 参数是十进制指数，不是数值边界 |
| `("discrete_uniform", low, high)` | 整数均匀分布 | 上界 `high` 包含在内 |
| `("bool", p)` / `("bern", p)` | Bernoulli bool | `p` 应在 `[0, 1]` |
| `("choice", values[, probs])` | 从 values 选一个值 | probs 可省略 |
| `("categorical", *weights)` | 返回类别 index | 也可写 `"cat"` |
| `("weighted_choice", (w1, v1), ...)` | 按权重选择并递归解析 value | value 本身可以是另一条规格 |
| `("spherical_sample", min_deg, max_deg)` | 球面均匀方向对应的 elevation 角 | 任一边界可为 `None` |

示例：

```python
width_spec = ("clip_gaussian", 0.9, 0.15, 0.6, 1.3)
style_spec = (
    "weighted_choice",
    (0.65, "flat"),
    (0.25, "raised"),
    (0.10, ("choice", ["glass", "louver"])),
)

width = random_general(width_spec)
style = random_general(style_spec)
```

不要让 agent 自创操作名；未知操作不会报错，而是悄悄返回原 tuple/list，错误可能延迟到 Blender 参数赋值时才出现。

## 常用分布函数

### `log_uniform`

签名：

```python
log_uniform(low, high, size=None)
```

在 log space 均匀采样后取指数。适合跨数量级变化的正值，如细节尺度、噪声 scale 或很小的 thickness；不适合可能为零或负数的参数。

### `clip_gaussian`

签名：

```python
clip_gaussian(mean, std, min, max, max_tries=20)
```

反复从正态分布采样，直到值位于闭区间 `[min, max]`。达到尝试上限后发出 warning，并将最后一次样本 clip 到边界。

```python
panel_thickness = clip_gaussian(0.025, 0.006, 0.012, 0.045)
```

当 mean 距区间很远或 std 极小时，结果容易集中在边界；此时应重新设计分布，而不是只增加 `max_tries`。

### `weighted_sample`

签名：

```python
weighted_sample(reg)
```

`reg` 是 `(value, weight)` 序列。函数归一化 weights，并返回一个 value。

```python
profile = weighted_sample([
    ("square", 4.0),
    ("round", 2.0),
    ("arched", 1.0),
])
```

weights 应为非负值且总和大于零。该函数不返回 index；需要 index 时使用 `np.random.choice`。

### `mixture_of_gaussian`

签名：

```python
mixture_of_gaussian(
    means,
    stds,
    weights,
    clamp_min=None,
    clamp_max=None,
)
```

先按 weights 选择一个高斯分量，再从对应 `mean` / `std` 采样。`clamp_min` 和 `clamp_max` 是采样后的硬截断，会在边界产生概率堆积。

### `wrap_gaussian`

签名：

```python
wrap_gaussian(mean, std, low=0, high=1)
```

从正态分布采样后把越界值周期性 wrap 回区间。适合 hue、相位和周期角度；要求 `high > low`，不适合普通尺寸参数。

## 间距与基础数学

| 函数 | 签名 | 行为与限制 |
| --- | --- | --- |
| `randomspacing` | `randomspacing(min, max, n, margin)` | 将区间分成 `n` 个 bucket，每个 bucket 采一个有序位置；`margin` 是 bucket 比例且必须在 `[0, 0.5]` |
| `lerp` | `lerp(a, b, x)` | 返回 `(1-x)*a + x*b`；支持标量和 NumPy 广播 |
| `round_to_nearest` | `round_to_nearest(x, step)` | 将值取整到最近的 step；`step` 不应为零 |
| `normalize` | `normalize(v, disallow_zero_norm=False, in_place=True)` | 对形状为 `(N, D)` 的向量批次沿最后一维归一化；默认会修改输入 array，零向量保持不变 |

安全的 normalize 用法：

```python
directions = normalize(vectors.astype(float), in_place=False)
```

整数 array 不适合原地除法。源码实现按向量批次索引，单个 `(D,)` 向量应先扩为 `v[None, :]`，归一化后再取第一个元素。必须拒绝零向量时设置 `disallow_zero_norm=True`。

`randomspacing` 在 `margin < 0.5` 时才执行 bucket 内随机偏移；当前实现中 `margin=0.5` 会返回各 bucket 起点，而不是中心。需要确定性中心时直接使用 `np.linspace` 加半个 bucket。

## 低频与上下文敏感函数

| 接口 | 原因 |
| --- | --- |
| `AddedSeed` | 它通过消耗当前 RNG 状态来偏移序列，并不设置独立 seed；资产代码中几乎没有使用 |
| `sample_json_palette` / `("palette", ...)` | 依赖 `infinigen_examples/configs_nature/palette`，不是静态室内资产的通用颜色来源；接口仍保留供自然资产使用 |
| `random_vector3` | 返回三个 `[0, 998]` 整数组成的 Vector，更像随机标识而不是几何方向 |
| `random_color` | 无约束 RGB 常产生不协调颜色；材质应使用 material API 或受控 palette |
| `dict_convex_comb` | 当前实现的 key 校验存在问题，不建议 generated code 调用 |
| `rotate_match_directions` | 对方向完全相反的向量会退化为 identity，不适合作为通用旋转对齐 API |

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 只设置 `np.random.seed`，却同时调用 Python `random` | 使用 `FixedSeed` |
| 在建模分支中临时增加随机调用，导致后续参数变化 | 集中采样参数，或用 `int_hash` 派生组件 seed |
| 对 thickness 使用包含负值的 normal | 使用 `clip_gaussian` 或正值 `log_uniform` |
| 把 `weighted_sample` 的 tuple 顺序写成 `(weight, value)` | 正确顺序是 `(value, weight)` |
| 将 `power_uniform` 参数当数值边界 | 参数是 base-10 exponent |
| 默认 `normalize` 不会修改输入 | 需要保留输入时传 `in_place=False` |
