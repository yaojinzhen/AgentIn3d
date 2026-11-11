# 文本几何节点

本文档覆盖室内资产源码高频使用、但未收入 `Nodes` 枚举的字符串拼接与文字转曲线节点。主要用于家电标签、按钮文字和动态 attribute 名称。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `"GeometryNodeStringJoin"` | 用分隔符拼接任意数量的字符串 |
| `"GeometryNodeStringToCurves"` | 将文字转换为逐字符 curve instances |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。通用 `new_node` 参数与 multi-input 规则见 `../node_wrangler_usage.md`。

## `"GeometryNodeStringJoin"`

**作用**：按 multi-input 的连接顺序拼接字符串，可构造标签或动态 named attribute 名称。

**创建方式**：

```python
name = nw.new_node(
    "GeometryNodeStringJoin",
    input_kwargs={"Delimiter": "_", "Strings": ["panel", suffix]},
).outputs["String"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | raw `GeometryNodeStringJoin`；`Nodes` 中没有对应成员 |
| `input_kwargs` | `Delimiter`、`Strings`（multi-input，可传字符串/socket 列表） |

**Input Sockets**：`Delimiter`（String）；`Strings`（String multi-input）。

**Output Sockets**：`String`。

分隔符只插入相邻项之间；拼接顺序由 multi-input 连接顺序决定。固定字符串在 Python 中直接拼接更简单，本节点用于至少一项是动态 String socket 的情况。

## `"GeometryNodeStringToCurves"`

**作用**：把字符串转换为每字符一个实例的 curve geometry，适合生成标签和刻字。

**创建方式**：

```python
text = nw.new_node(
    "GeometryNodeStringToCurves",
    input_kwargs={"String": "OPEN", "Size": 0.04},
    attrs={"align_x": "CENTER", "align_y": "BOTTOM_BASELINE"},
)
glyphs = text.outputs["Curve Instances"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | raw `GeometryNodeStringToCurves`；`Nodes` 中没有对应成员 |
| `attrs` | `overflow`、`align_x`、`align_y`、`pivot_mode`；可选 `font` data-block |
| `input_kwargs` | `String`、`Size`、`Character Spacing`、`Word Spacing`、`Line Spacing`、`Text Box Width`；部分 overflow 模式启用 `Text Box Height` |

**Input Sockets**：上述字符串、尺寸、间距和文本框输入。

**Output Sockets**：`Curve Instances`、`Line`、`Pivot Point`；`overflow="TRUNCATE"` 还启用 `Remainder`。

| attr | 常用值 |
| --- | --- |
| `overflow` | `OVERFLOW`、`SCALE_TO_FIT`、`TRUNCATE` |
| `align_x` | `LEFT`、`CENTER`、`RIGHT`、`JUSTIFY`、`FLUSH` |
| `align_y` | `TOP`、`TOP_BASELINE`、`MIDDLE`、`BOTTOM_BASELINE`、`BOTTOM` |
| `pivot_mode` | `MIDPOINT` 或 `TOP_*`/`BOTTOM_*` 七种位置 |

输出按字符实例化，相同字符共享底层 curve。常见实体文字流程是 `StringToCurves -> FillCurve -> ExtrudeMesh`；需要逐字符修改真实几何时先 `RealizeInstances`。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 把动态 String socket 用 Python `+` 拼接 | 使用 String Join |
| 文字只有轮廓没有厚度 | 接 `FillCurve`，再用 `ExtrudeMesh` 增加厚度 |
| 逐字符 mesh 操作没有效果 | 输出是 instances；先使用 `RealizeInstances` |
| `Remainder` 或 Text Box Height 不可用 | 先把 `overflow` 设为 `TRUNCATE` 或对应文本框模式 |
| 多行文字基线位置异常 | 明确设置 `align_y`，家电标签常用 `BOTTOM_BASELINE` |

## 相关文档

- `new_node` 与 multi-input：`../node_wrangler_usage.md`
- 填充与挤出文字：`curve_conversion_shape_nodes.md`、`mesh_operations_nodes.md`
- 实现逐字符实例：`instance_nodes.md`
- 将动态名称写入 attribute：`attribute_field_nodes.md`

## 主要来源

- `infinigen/assets/objects/appliances/beverage_fridge.py`
- `infinigen/assets/objects/appliances/dishwasher.py`
- `infinigen/assets/objects/appliances/microwave.py`
- `infinigen/assets/objects/elements/doors/joint_utils.py`
- [Blender 4.2 Text Utility Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/utilities/text/index.html)
- [Blender Join Strings](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/utilities/text/join_strings.html)
- [Blender String to Curves](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/utilities/text/string_to_curves.html)
