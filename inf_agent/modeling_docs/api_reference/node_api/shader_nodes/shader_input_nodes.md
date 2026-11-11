# Shader 输入节点

本文档覆盖 `ShaderNodeTree` 中的属性、坐标、几何、视角和光路输入，示例以 Material node tree 为主。每个节点的参数表只列当前节点实际需要的 `new_node` 参数；通用参数语义见 `../node_wrangler_usage.md`。

## 快速选择

| 节点 | 何时使用 |
| --- | --- |
| `Nodes.Attribute` | 按名称读取 geometry attribute、object property 或 instancer 数据 |
| `Nodes.ObjectInfo_Shader` | 读取当前物体/实例的随机值、位置、显示颜色和 pass index |
| `Nodes.TextureCoord` | 获取 Generated、Object、活动 UV、Camera 等常用纹理坐标 |
| `Nodes.UVMap` | 明确读取指定名称的 UV map |
| `Nodes.NewGeometry` | 读取 shading point 的世界位置、法线、朝向和 mesh 岛随机值 |
| `Nodes.AmbientOcclusion` | 用邻近遮挡生成污渍或缝隙 mask |
| `Nodes.Fresnel` | 根据 IOR 和视角生成物理含义明确的反射权重 |
| `Nodes.LayerWeight` | 生成便于艺术控制的掠射角/正视角混合权重 |
| `Nodes.LightPath` | 按 camera、shadow、reflection 等 ray 类型切换 shader |
| `Nodes.CurvesInfo` | 读取毛发/曲线 strand 的根尖位置、长度和随机值 |

这些节点不用于 Geometry 或 Compositor node tree；`TextureCoord`、`LightPath` 等可在 World node tree 复用，其余 object/geometry 相关输出主要用于 Material。接口以 Blender 4.2 为准；单体室内资产优先使用前五项，光路、AO 和曲线信息应按渲染器能力谨慎使用。

## `Nodes.Attribute`

**作用**：按名称读取当前 shading object、geometry、instancer 或 view layer 上的数据。最常用于读取 Geometry Nodes 写入的材质 mask、颜色和局部坐标。

**创建方式**：

```python
mask = nw.new_node(
    Nodes.Attribute,
    attrs={"attribute_name": "panel_mask", "attribute_type": "GEOMETRY"},
).outputs["Fac"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Attribute`，对应 `ShaderNodeAttribute` |
| `attrs` | `attribute_name: str`；`attribute_type` 为 `GEOMETRY`、`OBJECT`、`INSTANCER` 或 `VIEW_LAYER` |

**Input Sockets**：无。

**Output Sockets**：`Color`（RGBA）；`Vector`（XYZ）；`Fac`（标量）；`Alpha`。同一 attribute 会按目标 socket 类型转换，选择与数据语义匹配的输出即可。

| `attribute_type` | 数据来源 |
| --- | --- |
| `GEOMETRY` | mesh、curve 或 volume 的命名 attribute；项目默认且最常用 |
| `OBJECT` | object/data-block 的数值 custom property 或 RNA path |
| `INSTANCER` | instancer 数据；不可用时回退到 object |
| `VIEW_LAYER` | 当前 view layer 的数值 custom property；资产材质通常不需要 |

attribute 名称区分大小写。生成几何时必须保留对应 named attribute；缺失属性会得到回退值而非报错，容易产生“材质正常运行但 mask 全黑”的隐蔽错误。

## `Nodes.ObjectInfo_Shader`

**作用**：读取当前被着色物体或实例的信息，尤其适合让共享同一材质的多个实例获得稳定变化。

**创建方式**：

```python
instance_random = nw.new_node(
    Nodes.ObjectInfo_Shader
).outputs["Random"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.ObjectInfo_Shader`，对应 `ShaderNodeObjectInfo` |

**Input Sockets**：无。

**Output Sockets**：

| Socket | 说明 |
| --- | --- |
| `Location` | object 的世界空间位置 |
| `Color` / `Alpha` | Object Properties 中的 viewport display color 及其 alpha |
| `Object Index` | object pass index |
| `Material Index` | material pass index |
| `Random` | 每个 object instance 的 `[0, 1]` 稳定随机值 |

不要与 Geometry Nodes 的 `Nodes.ObjectInfo` 混用：后者有 `Object` 输入并输出 geometry/transform，本节点没有输入，只描述当前 shading instance。

## `Nodes.TextureCoord`

**作用**：提供程序纹理和图像纹理所需的常用坐标系。室内硬表面材质通常从 `Object`、`Generated` 或 `UV` 中选择。

**创建方式**：

```python
coordinates = nw.new_node(Nodes.TextureCoord)
object_coord = coordinates.outputs["Object"]
```

指定外部 object（常用 Empty）控制纹理坐标：

```python
coordinates = nw.new_node(
    Nodes.TextureCoord,
    attrs={"object": control_obj},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.TextureCoord`，对应 `ShaderNodeTexCoord` |
| `attrs` | 可选 `object: bpy.types.Object`；可选 `from_instancer: bool` |

**Input Sockets**：无。

**Output Sockets**：

| Socket | 说明 |
| --- | --- |
| `Generated` | 未形变包围盒内的自动 `[0, 1]` 坐标；无需 UV |
| `Normal` | object-space normal |
| `UV` | active render UV map |
| `Object` | shading object 或 `attrs["object"]` 定义的 object-space 坐标 |
| `Camera` | camera-space 坐标 |
| `Window` | 屏幕空间坐标，水平和垂直范围通常为 `[0, 1]` |
| `Reflection` | reflection vector，常用于 environment texture |

程序纹理需要跟随物体时优先用 `Object`；需要自动归一化到每个物体包围盒时用 `Generated`；有明确展开时用 `UV`。`from_instancer=True` 主要影响实例的 `Generated`/`UV`，并受渲染器和实例方式限制。

## `Nodes.UVMap`

**作用**：读取指定名称的 UV map；当资产存在多个 UV 层时比 `TextureCoord.outputs["UV"]` 更明确。

**创建方式**：

```python
uv = nw.new_node(
    Nodes.UVMap,
    attrs={"uv_map": "UVMap"},
).outputs["UV"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.UVMap`，对应 `ShaderNodeUVMap` |
| `attrs` | `uv_map: str`；可选 `from_instancer: bool` |

**Input Sockets**：无。

**Output Sockets**：`UV`（Vector）。

`uv_map` 为空时使用 active render UV map。命名层不存在时不会自动创建 UV；程序化资产若没有 UV 展开，应改用 `TextureCoord.Object/Generated`，不要假设存在默认层。

## `Nodes.NewGeometry`

**作用**：读取当前 shading point 的几何信息。常用于基于位置/法线的程序纹理、边缘磨损和正反面材质切换。

**创建方式**：

```python
geometry = nw.new_node(Nodes.NewGeometry)
position = geometry.outputs["Position"]
normal = geometry.outputs["Normal"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.NewGeometry`，对应 `ShaderNodeNewGeometry` |

**Input Sockets**：无。

**Output Sockets**：

| Socket | 说明 |
| --- | --- |
| `Position` | shading point 的世界空间位置 |
| `Normal` / `True Normal` | shading normal（含 smooth/bump）/ 原始几何法线 |
| `Tangent` | 表面切线 |
| `Incoming` | 到达 shading point 的入射方向 |
| `Parametric` | 表面参数坐标 |
| `Backfacing` | 背面为 1，正面为 0 |
| `Pointiness` | 近似 mesh 曲率；Cycles only |
| `Random Per Island` | 每个 connected mesh island 的随机值；Cycles only |

`Position` 等向量使用世界空间：物体移动后基于它的纹理会停留在世界中。需要纹理固定在物体上时改用 `TextureCoord.Object`。

## `Nodes.AmbientOcclusion`

**作用**：估计 shading point 周围的几何遮挡，生成接触阴影、缝隙污渍或内凹区域 mask。

**创建方式**：

```python
ao = nw.new_node(
    Nodes.AmbientOcclusion,
    input_kwargs={"Distance": 0.08},
    attrs={"samples": 16, "only_local": True},
)
mask = ao.outputs["AO"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.AmbientOcclusion`，对应 `ShaderNodeAmbientOcclusion` |
| `input_kwargs` | `Color`、`Distance`、`Normal` |
| `attrs` | 可选 `samples: int`、`inside: bool`、`only_local: bool` |

**Input Sockets**：`Color`（被 AO 调制的颜色）；`Distance`（参与遮挡的最大距离）；`Normal`（查询方向）。

**Output Sockets**：`Color`（输入颜色应用 AO 后的结果）；`AO`（0 到 1 的遮挡因子）。

该节点依赖渲染器，OSL 不支持；`samples` 越大通常越慢。单体资产优先将 `Distance` 设为与缝隙尺度相近的小值，并用 `only_local=True` 避免附近其他物体改变材质外观。

## `Nodes.Fresnel`

**作用**：根据表面法线、视角和折射率计算 dielectric Fresnel 反射权重。

**创建方式**：

```python
fresnel = nw.new_node(
    Nodes.Fresnel,
    input_kwargs={"IOR": 1.5},
).outputs["Fac"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Fresnel`，对应 `ShaderNodeFresnel` |
| `input_kwargs` | `IOR`、可选 `Normal` |

**Input Sockets**：`IOR`（进入材质的折射率，默认 1.5）；`Normal`（可接 normal/bump 结果）。

**Output Sockets**：`Fac`（反射概率权重，掠射角通常更高）。

需要有物理含义的玻璃或涂层混合时用 Fresnel；只需要可调的视角渐变时用 `LayerWeight`。

## `Nodes.LayerWeight`

**作用**：生成面向视角和掠射角之间的艺术化混合权重，适合边缘染色、涂层和非物理风格控制。

**创建方式**：

```python
facing = nw.new_node(
    Nodes.LayerWeight,
    input_kwargs={"Blend": 0.3},
).outputs["Facing"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.LayerWeight`，对应 `ShaderNodeLayerWeight` |
| `input_kwargs` | `Blend`、可选 `Normal` |

**Input Sockets**：`Blend`（偏置权重，范围 0 到 1）；`Normal`。

**Output Sockets**：`Fresnel`（便于控制的 dielectric Fresnel 权重）；`Facing`（正视到掠射角的渐变）。

## `Nodes.LightPath`

**作用**：判断 shader 当前针对哪类 ray 执行，用于相机可见性、阴影、反射和折射路径的条件切换。

**创建方式**：

```python
is_camera = nw.new_node(
    Nodes.LightPath
).outputs["Is Camera Ray"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.LightPath`，对应 `ShaderNodeLightPath` |

**Input Sockets**：无。

**Output Sockets**：

| 类别 | Sockets |
| --- | --- |
| ray 类型 | `Is Camera Ray`、`Is Shadow Ray`、`Is Diffuse Ray`、`Is Glossy Ray`、`Is Singular Ray`、`Is Reflection Ray`、`Is Transmission Ray` |
| 距离/深度 | `Ray Length`、`Ray Depth`、`Diffuse Depth`、`Glossy Depth`、`Transparent Depth`、`Transmission Depth` |

类型输出为 0/1 Float，深度输出为 bounce 次数。Eevee 只近似支持其中一部分；仅在明确需要“对相机与其他 ray 使用不同 shader”时使用，并检查目标渲染器结果。

## `Nodes.CurvesInfo`

**作用**：读取当前被着色 hair/curve strand 的信息。当前 Infinigen 源码未直接调用，普通室内物体通常无需使用，但接口仍保留供 hair/curves 材质使用。

**创建方式**：

```python
strand = nw.new_node(Nodes.CurvesInfo)
root_to_tip = strand.outputs["Intercept"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CurvesInfo`，对应 `ShaderNodeHairInfo` |

**Input Sockets**：无。

**Output Sockets**：`Is Strand`（strand 上为 1）；`Intercept`（根部 0、尖端 1）；`Length`；`Thickness`；`Tangent Normal`；`Random`（每条 strand 的稳定随机值）。

这些输出只在曲线/毛发 shading 上有明确意义。布艺的普通 mesh 纤维纹理应使用坐标与程序纹理节点，不应仅为纹理外观引入 hair geometry。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 用 `Nodes.ObjectInfo` 读取材质实例随机值 | Shader 中使用 `Nodes.ObjectInfo_Shader.outputs["Random"]` |
| 用 `NamedAttribute` 读取材质 attribute | `NamedAttribute` 属于 Geometry Nodes；Shader 中使用 `Nodes.Attribute` |
| 程序纹理随物体移动而滑动 | 不要用 world-space `NewGeometry.Position`；改用 `TextureCoord.Object` |
| 多 UV 层仍使用 `TextureCoord.UV` | 用 `Nodes.UVMap` 并设置准确的 `uv_map` 名称 |
| AO 被附近场景物体改变 | 为单体材质设置 `only_local=True`，并限制 `Distance` |
| 假设所有 Light Path 输出在 Eevee 中等价可用 | 按目标渲染器验证；复杂 ray 路径逻辑优先面向 Cycles |
| 把 Fresnel 与 Facing 当成固定 mesh mask | 两者随视角变化；固定区域应使用 geometry attribute |

## 相关文档

- 节点创建与 socket 连接：`../node_wrangler_usage.md`
- named attribute 的写入：`../geometry_nodes/attribute_field_nodes.md`
- 坐标映射与旋转：`../common_nodes/vector_rotation_mapping_nodes.md`
- 程序纹理：`../common_nodes/texture_nodes.md`
- normal、bump 与 displacement：`displacement_normal_nodes.md`
- Principled BSDF：`principled_bsdf_node.md`
- 专用 BSDF 与 shader 混合：`surface_bsdf_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- `infinigen/assets/materials/lamp_shaders.py`
- `infinigen/assets/materials/dishwasher_shaders.py`
- `infinigen/assets/materials/wear_tear/edge_wear.py`
- `infinigen/assets/materials/ceramic/brick.py`
- [Blender 4.2 Shader Input Nodes](https://docs.blender.org/manual/en/4.2/render/shader_nodes/input/index.html)
- [Blender 4.2 Attribute Node](https://docs.blender.org/manual/en/4.2/render/shader_nodes/input/attribute.html)
- [Blender 4.2 Texture Coordinate Node](https://docs.blender.org/manual/en/4.2/render/shader_nodes/input/texture_coordinate.html)
- [Blender 4.2 Geometry Node](https://docs.blender.org/manual/en/4.2/render/shader_nodes/input/geometry.html)
- [Blender 4.2 Light Path Node](https://docs.blender.org/manual/en/4.2/render/shader_nodes/input/light_path.html)
