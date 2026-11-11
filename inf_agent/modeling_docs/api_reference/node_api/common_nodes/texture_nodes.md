# 纹理节点

本文档覆盖程序纹理、图像采样和环境纹理节点。参数表只列当前节点实际使用的 `new_node` 参数；通用语义见 `../node_wrangler_usage.md`。

## 快速选择

| 节点 | 作用 | Node tree |
| --- | --- | --- |
| `Nodes.NoiseTexture` | 连续分形噪声 | Shader、Geometry |
| `Nodes.MusgraveTexture` | 旧 Musgrave 兼容入口 | 转为 Noise Texture |
| `Nodes.VoronoiTexture` | 单元格、边缘和最近点距离 | Shader、Geometry |
| `Nodes.WaveTexture` | 条带或同心环 | Shader、Geometry |
| `Nodes.WhiteNoiseTexture` | 每个坐标独立的随机值 | Shader、Geometry |
| `Nodes.ImageTexture` | 以 Image socket 采样图像 | Geometry |
| `Nodes.GradientTexture` | 从坐标生成解析渐变 | Shader、Geometry |
| `Nodes.ShaderImageTexture` | 采样 `bpy.types.Image` | Shader |
| `Nodes.MagicTexture` | 彩色湍流纹理 | Shader、Geometry |
| `Nodes.BrickTexture` | 砖块/砌体图案 | Shader、Geometry |
| `Nodes.CheckerTexture` | 两色棋盘格 | Shader、Geometry |
| `Nodes.EnvironmentTexture` | 经纬或镜面球环境贴图 | Shader |

接口以 Blender 4.2 为准。程序纹理应显式传入 `Vector`（1D 模式传 `W`），避免依赖 Shader 的 Generated 坐标或 Geometry 的隐式 Position；这样资产在不同上下文中更可复现。

## `Nodes.NoiseTexture`

**作用**：生成连续的多尺度噪声，用于颜色、粗糙度、位移和几何扰动。

**创建方式**：

```python
noise = nw.new_node(
    Nodes.NoiseTexture,
    input_kwargs={
        "Vector": position,
        "Scale": 6.0,
        "Detail": 4.0,
        "Roughness": 0.6,
    },
    attrs={"noise_dimensions": "3D", "noise_type": "FBM"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.NoiseTexture`，对应 `ShaderNodeTexNoise` |
| `attrs` | `noise_dimensions`、`noise_type`；可选 `normalize` |
| `input_kwargs` | 当前维度和噪声类型启用的 sockets |

**Input Sockets**：

| 条件 | Inputs |
| --- | --- |
| `1D` | `W`、`Scale`、`Detail`、`Roughness`、`Lacunarity`、`Distortion` |
| `2D`/`3D` | `Vector` 加上述参数（无 `W`） |
| `4D` | `Vector`、`W` 加上述参数 |
| `RIDGED_MULTIFRACTAL`/`HYBRID_MULTIFRACTAL` | 额外启用 `Offset`、`Gain` |
| `HETERO_TERRAIN` | 额外启用 `Offset` |

`noise_type` 可为 `FBM`、`MULTIFRACTAL`、`RIDGED_MULTIFRACTAL`、`HYBRID_MULTIFRACTAL`、`HETERO_TERRAIN`。

**Output Sockets**：`Fac`（Float）、`Color`。

需要可调随机种子时使用 `4D` 并改变 `W`；`node_utils.noise(...)` 是 Infinigen 的 4D 随机噪声 helper。

## `Nodes.MusgraveTexture`

**作用**：读取旧 Infinigen 代码；Blender 4.2 已无独立 Musgrave 节点。

**创建方式**：

```python
legacy = nw.new_node(
    Nodes.MusgraveTexture,
    input_kwargs={
        "Vector": position,
        "Scale": 5.0,
        "Detail": 3.0,
        "Dimension": 2.0,
        "Lacunarity": 2.0,
    },
    attrs={"musgrave_dimensions": "3D", "musgrave_type": "FBM"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MusgraveTexture`，兼容层实际创建 `Nodes.NoiseTexture` |
| `attrs` | 旧 `musgrave_dimensions`、`musgrave_type` |
| `input_kwargs` | 旧 Musgrave sockets；由兼容层改写 |
| `compat_mode` | 必须保持默认 `True` |

**Input Sockets**：兼容输入为 `Vector`、`W`、`Scale`、`Detail`、`Dimension`、`Lacunarity`、`Offset`、`Gain`；转换后使用 Noise Texture 的当前 sockets。

**Output Sockets**：实际节点的 `Fac`、`Color`。

新生成代码直接使用 `NoiseTexture`。兼容转换会调整 `Detail`，由 `Dimension` 和 `Lacunarity` 计算 `Roughness`，并设置 `normalize=False`；它是近似迁移，不保证逐像素一致。

## `Nodes.VoronoiTexture`

**作用**：计算 Worley/Voronoi 单元的距离、边缘、最近点位置或内接球半径。

**创建方式**：

```python
cells = nw.new_node(
    Nodes.VoronoiTexture,
    input_kwargs={"Vector": position, "Scale": 8.0, "Randomness": 0.8},
    attrs={
        "voronoi_dimensions": "3D",
        "feature": "DISTANCE_TO_EDGE",
        "distance": "EUCLIDEAN",
    },
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.VoronoiTexture`，对应 `ShaderNodeTexVoronoi` |
| `attrs` | `voronoi_dimensions`、`feature`、`distance`；可选 `normalize` |
| `input_kwargs` | 当前维度、feature 和距离模式启用的 sockets |

**Input Sockets**：`1D` 使用 `W`，`2D`/`3D` 使用 `Vector`，`4D` 同时使用两者；常用参数为 `Scale`、`Detail`、`Roughness`、`Lacunarity`、`Randomness`。`SMOOTH_F1` 增加 `Smoothness`，`distance="MINKOWSKI"` 增加 `Exponent`。

**Output Sockets**：

| `feature` | Outputs |
| --- | --- |
| `F1`、`F2`、`SMOOTH_F1` | `Distance`、`Color`、`Position`；1D/4D 还可输出 `W` |
| `DISTANCE_TO_EDGE` | `Distance` |
| `N_SPHERE_RADIUS` | `Radius` |

`distance` 可为 `EUCLIDEAN`、`MANHATTAN`、`CHEBYCHEV`、`MINKOWSKI`。选择边缘 mask 时优先 `DISTANCE_TO_EDGE`，不要再从 `Color` 猜测边界。

## `Nodes.WaveTexture`

**作用**：生成规则条带或同心环，并可叠加噪声扭曲。

**创建方式**：

```python
stripes = nw.new_node(
    Nodes.WaveTexture,
    input_kwargs={"Vector": mapped, "Scale": 12.0, "Distortion": 1.5},
    attrs={
        "wave_type": "BANDS",
        "bands_direction": "X",
        "wave_profile": "SIN",
    },
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.WaveTexture`，对应 `ShaderNodeTexWave` |
| `attrs` | `wave_type`、`bands_direction`/`rings_direction`、`wave_profile` |
| `input_kwargs` | `Vector`、`Scale`、`Distortion`、`Detail`、`Detail Scale`、`Detail Roughness`、`Phase Offset` |

**Input Sockets**：见参数表；`Phase Offset` 沿传播方向移动图案。

**Output Sockets**：`Color`、`Fac`。

`wave_type` 为 `BANDS` 或 `RINGS`；band 方向为 `X`/`Y`/`Z`/`DIAGONAL`，ring 方向为 `X`/`Y`/`Z`/`SPHERICAL`，profile 为 `SIN`/`SAW`/`TRI`。

## `Nodes.WhiteNoiseTexture`

**作用**：把坐标哈希成不连续随机值，适合逐点变化，不适合连续表面起伏。

**创建方式**：

```python
random_field = nw.new_node(
    Nodes.WhiteNoiseTexture,
    input_kwargs={"Vector": position, "W": seed},
    attrs={"noise_dimensions": "4D"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.WhiteNoiseTexture`，对应 `ShaderNodeTexWhiteNoise` |
| `attrs` | `noise_dimensions`：`1D`/`2D`/`3D`/`4D` |
| `input_kwargs` | `1D` 使用 `W`；`2D`/`3D` 使用 `Vector`；`4D` 两者都用 |

**Input Sockets**：`Vector` 和/或 `W`，由维度决定。

**Output Sockets**：`Value`（Float）、`Color`。

相邻坐标会产生无关值；需要平滑纹理时使用 `NoiseTexture`。

## `Nodes.ImageTexture`

**作用**：在 Geometry Nodes 中采样由 Image socket 提供的图像或序列帧。

**创建方式**：

```python
sampled = nw.new_node(
    Nodes.ImageTexture,
    input_kwargs={"Image": image_socket, "Vector": uvw, "Frame": frame},
    attrs={"interpolation": "Linear", "extension": "REPEAT"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.ImageTexture`，对应 `GeometryNodeImageTexture` |
| `attrs` | `interpolation`：`Linear`/`Closest`/`Cubic`；`extension` |
| `input_kwargs` | `Image`（Image socket）、`Vector`、`Frame` |

**Input Sockets**：`Image`、`Vector`、`Frame`（Integer）。

**Output Sockets**：`Color`、`Alpha`。

`extension` 可为 `REPEAT`、`EXTEND`、`CLIP`、`MIRROR`。`Image` 是 node socket，不是 `attrs={"image": ...}`；普通 `bpy.types.Image` 数据块应改用 Shader Image Texture，或先通过 nodegroup interface 暴露为 Image socket。

## `Nodes.GradientTexture`

**作用**：从输入坐标生成无噪声的解析渐变。

**创建方式**：

```python
gradient = nw.new_node(
    Nodes.GradientTexture,
    input_kwargs={"Vector": mapped},
    attrs={"gradient_type": "LINEAR"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.GradientTexture`，对应 `ShaderNodeTexGradient` |
| `attrs` | `gradient_type` |
| `input_kwargs` | `Vector` |

**Input Sockets**：`Vector`。

**Output Sockets**：`Color`、`Fac`。

`gradient_type` 可为 `LINEAR`、`QUADRATIC`、`EASING`、`DIAGONAL`、`SPHERICAL`、`QUADRATIC_SPHERE`、`RADIAL`。通常先用 Mapping/VectorMath 控制方向和尺度。

## `Nodes.ShaderImageTexture`

**作用**：在 Shader tree 中采样 `bpy.types.Image` 数据块。

**创建方式**：

```python
image_tex = nw.new_node(
    Nodes.ShaderImageTexture,
    input_kwargs={"Vector": uv},
    attrs={
        "image": image,
        "interpolation": "Linear",
        "projection": "FLAT",
        "extension": "REPEAT",
    },
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.ShaderImageTexture`，对应 `ShaderNodeTexImage` |
| `attrs` | `image`、`interpolation`、`projection`、`extension`；BOX 可设 `projection_blend` |
| `input_kwargs` | `Vector` |

**Input Sockets**：`Vector`。

**Output Sockets**：`Color`、`Alpha`。

`interpolation` 可为 `Linear`、`Closest`、`Cubic`、`Smart`；`projection` 可为 `FLAT`、`BOX`、`SPHERE`、`TUBE`。颜色贴图与非颜色数据应在 `image.colorspace_settings` 层设置正确色彩空间。

## `Nodes.MagicTexture`

**作用**：生成彩色湍流图案；适合装饰效果，不是通用随机高度场。

**创建方式**：

```python
magic = nw.new_node(
    Nodes.MagicTexture,
    input_kwargs={"Vector": position, "Scale": 4.0, "Distortion": 1.0},
    attrs={"turbulence_depth": 3},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MagicTexture`，对应 `ShaderNodeTexMagic` |
| `attrs` | `turbulence_depth` |
| `input_kwargs` | `Vector`、`Scale`、`Distortion` |

**Input Sockets**：`Vector`、`Scale`、`Distortion`。

**Output Sockets**：`Color`、`Fac`。

## `Nodes.BrickTexture`

**作用**：生成交错砖块与灰缝，可用于砖墙、瓷砖和编织单元。

**创建方式**：

```python
bricks = nw.new_node(
    Nodes.BrickTexture,
    input_kwargs={
        "Vector": mapped,
        "Color1": color_a,
        "Color2": color_b,
        "Mortar": mortar_color,
        "Scale": 6.0,
        "Mortar Size": 0.02,
    },
    attrs={"offset": 0.5, "offset_frequency": 2},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.BrickTexture`，对应 `ShaderNodeTexBrick` |
| `attrs` | `offset`、`offset_frequency`、`squash`、`squash_frequency` |
| `input_kwargs` | `Vector`、三种颜色及尺寸/灰缝参数 |

**Input Sockets**：`Vector`、`Color1`、`Color2`、`Mortar`、`Scale`、`Mortar Size`、`Mortar Smooth`、`Bias`、`Brick Width`、`Row Height`。

**Output Sockets**：`Color`、`Fac`；`Fac` 区分砖体与灰缝。

高频图案用于 Geometry 字段时需要足够网格密度，否则会丢失细节。

## `Nodes.CheckerTexture`

**作用**：按三维坐标交替输出两种颜色。

**创建方式**：

```python
checker = nw.new_node(
    Nodes.CheckerTexture,
    input_kwargs={
        "Vector": mapped,
        "Color1": color_a,
        "Color2": color_b,
        "Scale": 8.0,
    },
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CheckerTexture`，对应 `ShaderNodeTexChecker` |
| `input_kwargs` | `Vector`、`Color1`、`Color2`、`Scale` |

**Input Sockets**：`Vector`、`Color1`、`Color2`、`Scale`。

**Output Sockets**：`Color`、`Fac`。

## `Nodes.EnvironmentTexture`

**作用**：用方向 Vector 采样 HDRI/环境图像，主要用于 World shader。

**创建方式**：

```python
environment = nw.new_node(
    Nodes.EnvironmentTexture,
    input_kwargs={"Vector": direction},
    attrs={
        "image": image,
        "projection": "EQUIRECTANGULAR",
        "interpolation": "Linear",
    },
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.EnvironmentTexture`，对应 `ShaderNodeTexEnvironment` |
| `attrs` | `image`、`projection`、`interpolation` |
| `input_kwargs` | `Vector` |

**Input Sockets**：`Vector`（采样方向）。

**Output Sockets**：`Color`。

`projection` 为 `EQUIRECTANGULAR` 或 `MIRROR_BALL`。单体资产生成通常不应修改 World；只有任务明确要求环境贴图时才使用。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 程序纹理不传坐标 | 显式传 `Vector`；4D 随机变化再传 `W` |
| 新代码继续创建 `MusgraveTexture` | 直接使用当前 `NoiseTexture` 参数 |
| 混用两个 Image Texture | Geometry 用 `Image` socket；Shader 用 `attrs={"image": image}` |
| 读取不存在的动态输出 | 先设置 Voronoi `feature`/维度，再按名称取 output |
| 用纹理频率代替几何分辨率 | 位移/selection 仍需足够采样点或细分 |

## 相关文档

- `new_node` 参数：`../node_wrangler_usage.md`
- Musgrave 兼容边界：`../socket_attrs_and_compatibility.md`
- 坐标映射：`vector_rotation_mapping_nodes.md`
- 颜色映射：`color_processing_nodes.md`
- Bump 与 displacement：`../shader_nodes/displacement_normal_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- `infinigen/core/nodes/node_utils.py`
- `infinigen/core/nodes/compatibility.py`
- [Blender 4.2 Texture Nodes](https://docs.blender.org/manual/en/4.2/render/shader_nodes/textures/index.html)
- [Blender 4.2 Noise Texture](https://docs.blender.org/manual/en/4.2/render/shader_nodes/textures/noise.html)
- [Blender 4.2 Voronoi Texture](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/texture/voronoi.html)
- [Blender 4.2 Wave Texture](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/texture/wave.html)
- [Blender 4.2 Image Texture](https://docs.blender.org/manual/en/4.2/render/shader_nodes/textures/image.html)
- [Blender 4.2 Musgrave Migration](https://docs.blender.org/manual/en/4.2/render/shader_nodes/textures/musgrave.html)
