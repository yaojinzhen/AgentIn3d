# Shader、World 与输出节点

本文档覆盖 Material、Light、World 的最终输出节点，以及构建世界背景的 Background 和 Sky Texture。资产材质通常只创建 `Nodes.MaterialOutput`；Light 和 World node tree 属于场景或 runner 职责。三类输出接口均完整记录，调用所有权不同不构成删除理由。

## 快速选择

| 目标 | 节点 | 所属 node tree |
| --- | --- | --- |
| 输出资产表面、体积、位移或 EEVEE 厚度 | `Nodes.MaterialOutput` | Material |
| 输出 Blender Light 的 emission shader | `Nodes.LightOutput` | Light |
| 输出世界背景和世界体积 | `Nodes.WorldOutput` | World |
| 创建程序天空颜色 | `Nodes.SkyTexture` | World |
| 把颜色、HDRI 或天空转换为 world shader | `Nodes.Background` | World |

三种 Output 不能混用。`MaterialOutput`、`LightOutput`、`WorldOutput` 在 Infinigen 的 `SINGLETON_NODES` 中；同一 node tree 中重复调用 `nw.new_node` 会复用已有同类节点，并继续改写它的 inputs 和 attrs。

## `Nodes.MaterialOutput`

**作用**：定义 material node tree 最终交给渲染器的表面、体积、位移和厚度信息。

**创建方式**：

```python
nw.new_node(
    Nodes.MaterialOutput,
    input_kwargs={
        "Surface": surface_shader,
        "Displacement": displacement,
    },
    attrs={"is_active_output": True, "target": "ALL"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MaterialOutput`，对应 `ShaderNodeOutputMaterial` |
| `input_kwargs` | `Surface`、`Volume`、`Displacement`、`Thickness` |
| `attrs` | 可选 `is_active_output: bool`；`target` 为 `ALL`、`EEVEE` 或 `CYCLES` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Surface` | Shader | BSDF、Emission 或 Mix Shader 的最终表面 closure |
| `Volume` | Shader | Principled Volume 等体积 closure；普通实体材质留空 |
| `Displacement` | Vector | Displacement 节点输出；真实位移或 bump 由 Infinigen render mode 决定 |
| `Thickness` | Float | Blender 4.2 EEVEE 的物体空间厚度近似；用于 SSS、Translucent 和 Refraction 等效果 |

**Output Sockets**：无。

`Thickness` 只供 EEVEE 使用。未连接时 EEVEE 根据物体最小尺寸估计厚度；连接 0 会禁用厚度近似。真实薄壳厚度应优先由几何表达，不要为了 Cycles 材质设置该输入。

`target="ALL"` 是资产代码的默认选择。若设为 `EEVEE` 或 `CYCLES`，Blender 可使用多个目标不同的 Material Output；但 `NodeWrangler` 的 singleton 机制不会新建第二个同类输出，因此生成代码不应通过重复 `new_node` 构建双渲染器分支。

## `Nodes.LightOutput`

**作用**：定义 Blender Light data-block 的最终发光 shader。

**创建方式**：

```python
emission = nw.new_node(
    Nodes.Emission,
    input_kwargs={"Color": light_color, "Strength": 500.0},
)
nw.new_node(
    Nodes.LightOutput,
    input_kwargs={"Surface": emission},
    attrs={"is_active_output": True, "target": "ALL"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.LightOutput`，对应 `ShaderNodeOutputLight` |
| `input_args` | 可按位置传 `[emission]` |
| `input_kwargs` | `Surface` |
| `attrs` | 可选 `is_active_output`；`target` 为 `ALL`、`EEVEE` 或 `CYCLES` |

**Input Sockets**：`Surface`（Shader），通常连接 `Nodes.Emission`。

**Output Sockets**：无。

本节点必须在 `light.data.node_tree` 中使用，不能放入资产 material。灯光对象的位置、类型、能量、尺寸和阴影设置不是本节点职责；单体资产通常只生成可发光材质或灯具几何，把真实 Light 的创建交给场景层。

## `Nodes.WorldOutput`

**作用**：定义当前 World 的环境表面和参与体积。

**创建方式**：

```python
background = nw.new_node(
    Nodes.Background,
    input_kwargs={"Color": world_color, "Strength": 0.2},
)
nw.new_node(
    Nodes.WorldOutput,
    input_kwargs={"Surface": background},
    attrs={"is_active_output": True, "target": "ALL"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.WorldOutput`，对应 `ShaderNodeOutputWorld` |
| `input_kwargs` | `Surface`、可选 `Volume` |
| `attrs` | 可选 `is_active_output`；`target` 为 `ALL`、`EEVEE` 或 `CYCLES` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Surface` | Shader | 通常连接 Background，决定环境颜色和环境照明 |
| `Volume` | Shader | 世界体积；会影响整场景，只有明确的大气流程才连接 |

**Output Sockets**：无。

本节点必须位于某个 `bpy.types.World.node_tree`；当前场景通常从 `bpy.context.scene.world.node_tree` 访问。资产 shader 不应创建或替换 World Output，否则单个资产会改变整场景的照明和背景。

## `Nodes.SkyTexture`

**作用**：根据太阳方向和大气参数生成程序天空颜色，通常连接 Background 的 `Color`。

**创建方式**：

```python
sky = nw.new_node(
    Nodes.SkyTexture,
    attrs={
        "sky_type": "NISHITA",
        "sun_elevation": np.radians(25.0),
        "sun_rotation": np.radians(120.0),
        "sun_size": np.radians(0.5),
        "sun_intensity": 1.0,
        "altitude": 100.0,
        "air_density": 1.0,
        "dust_density": 1.0,
        "ozone_density": 1.0,
    },
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SkyTexture`，对应 `ShaderNodeTexSky` |
| `input_kwargs` | 仅 `PREETHAM`/`HOSEK_WILKIE` 可选 `Vector` |
| `attrs` | `sky_type` 及下表中对应模型的属性 |

**Input Sockets**：`Vector`（Vector）。`PREETHAM` 和 `HOSEK_WILKIE` 可连接采样方向；`NISHITA` 下 Blender 4.2 会禁用或不暴露该 socket，不要传入。

**Output Sockets**：`Color`（RGBA），连接 `Nodes.Background.inputs["Color"]`。

| `sky_type` | 主要 attrs | 使用建议 |
| --- | --- | --- |
| `NISHITA` | `sun_disc`、`sun_size`、`sun_intensity`、`sun_elevation`、`sun_rotation`、`altitude`、`air_density`、`dust_density`、`ozone_density` | Infinigen 天空主路径，适合可控太阳和大气 |
| `PREETHAM` | `sun_direction`、`turbidity`、`ground_albedo` | 旧模型，适合维护已有节点图 |
| `HOSEK_WILKIE` | `sun_direction`、`turbidity`、`ground_albedo` | 旧模型，天空分布与 Preetham 不同 |

Python 属性中的 `sun_size`、`sun_elevation` 和 `sun_rotation` 使用弧度，不是 Blender UI 显示的角度；生成代码应使用 `np.radians`。`altitude` 是长度，Blender 4.2 范围为 `0-60000`；大气 density 通常以 1 表示清晰日间基准。

## `Nodes.Background`

**作用**：把颜色或纹理转换为世界背景 shader，并控制环境强度。

**创建方式**：

```python
background = nw.new_node(
    Nodes.Background,
    input_kwargs={
        "Color": sky.outputs["Color"],
        "Strength": 0.2,
    },
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Background`，对应 `ShaderNodeBackground` |
| `input_kwargs` | `Color`、`Strength` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Color` | Color | 常量颜色、Sky Texture 或 Environment Texture 输出 |
| `Strength` | Float | 环境颜色和照明强度的乘数 |

Blender 4.2 RNA 还会报告一个禁用的内部 `Weight` socket；它不是可写 API。

**Output Sockets**：`Background`（Shader），连接 `Nodes.WorldOutput.inputs["Surface"]`。

室内资产生成不应为了让单个物体“更亮”而提高 World Background；应调整材质、灯具资产或由 runner 配置统一照明。

## 常用组合

程序天空的完整 World 链路：

```python
sky = nw.new_node(
    Nodes.SkyTexture,
    attrs={
        "sky_type": "NISHITA",
        "sun_elevation": np.radians(20.0),
        "sun_rotation": np.radians(210.0),
    },
)
background = nw.new_node(
    Nodes.Background,
    input_kwargs={"Color": sky, "Strength": 0.2},
)
nw.new_node(
    Nodes.WorldOutput,
    input_kwargs={"Surface": background},
)
```

HDRI 世界不使用 Sky Texture：读取 `../common_nodes/texture_nodes.md` 中的 `Nodes.EnvironmentTexture`，再连接 Background 和 World Output。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 把 Material Output 放入 World 或 Light tree | 按 node tree 使用对应 Output |
| 重复 `nw.new_node(MaterialOutput)` 期待创建第二个输出 | singleton 会复用旧节点；资产保持一个 `target="ALL"` 输出 |
| 把 Sky Texture 直接接 World Output | 先用 Background 把 Color 转为 Shader |
| 给 Nishita 的 `Vector` 传值 | Blender 4.2 下该输入不可用且可能不出现在 inputs 中；使用太阳和大气 attrs |
| 将 `sun_elevation=30` 当作 30 度 | Python 属性使用弧度，应传 `np.radians(30)` |
| 把 Volume shader 接到 Material/World 的 `Surface` | 连接同一输出节点的 `Volume` |
| 在资产材质函数中重建 World | World 属于场景或 runner，资产只负责 Material Output |
| 用 Material Output `Thickness` 表示真实壁厚 | 它只是 EEVEE 近似；真实结构用几何 |

## 相关文档

- Principled BSDF：`principled_bsdf_node.md`
- 其他 Surface BSDF 与 Mix Shader：`surface_bsdf_nodes.md`
- Emission、Volume 与 Hair：`emission_volume_hair_nodes.md`
- Displacement：`displacement_normal_nodes.md`
- Environment Texture：`../common_nodes/texture_nodes.md`
- 材质创建与赋值：`../../function_api/surface_material_ops.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- `infinigen/assets/lighting/sky_lighting.py`
- `infinigen/assets/lighting/hdri_lighting.py`
- `infinigen/assets/lighting/indoor_lights.py`
- [Blender 4.2 Material Output](https://docs.blender.org/manual/en/4.2/render/shader_nodes/output/material.html)
- [Blender 4.2 Light Output](https://docs.blender.org/manual/en/4.2/render/shader_nodes/output/light.html)
- [Blender 4.2 World Output](https://docs.blender.org/manual/en/4.2/render/shader_nodes/output/world.html)
- [Blender 4.2 Sky Texture](https://docs.blender.org/manual/en/4.2/render/shader_nodes/textures/sky.html)
- [Blender 4.2 Background](https://docs.blender.org/manual/en/4.2/render/shader_nodes/shader/background.html)
