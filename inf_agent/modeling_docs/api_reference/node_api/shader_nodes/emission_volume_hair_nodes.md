# 发光、体积与毛发节点

本文档覆盖发光、体积和毛发 shader。三者的输出目标和适用几何不同：Emission 可接 Surface/Light Output，Principled Volume 接 Material Output 的 Volume，Principled Hair BSDF 接曲线/毛发对象的 Surface。

Blender 4.2 RNA 会为这些 shader 报告禁用的内部 `Weight` socket；它不是可写 API，本文档不将其列入 Input Sockets。

## 快速选择

| 目标 | 节点 | 输出接到 |
| --- | --- | --- |
| 灯光、发光面或独立 emission closure | `Nodes.Emission` | Material/Light Output 的 `Surface` |
| 烟、雾、火或均匀介质 | `Nodes.PrincipledVolume` | Material Output 的 `Volume` |
| 毛发、绒毛或皮毛曲线 | `Nodes.PrincipledHairBSDF` | Material Output 的 `Surface` |

普通面板弱发光也可直接使用 Principled BSDF 的 `Emission Color` 和 `Emission Strength`；需要独立混合或 Light node tree 时再使用 `Nodes.Emission`。

## `Nodes.Emission`

**作用**：创建不依赖入射光的发光 closure，可用于材质表面或 Blender Light 的节点树。

**创建方式**：

```python
emission = nw.new_node(
    Nodes.Emission,
    input_kwargs={
        "Color": (1.0, 0.35, 0.08, 1.0),
        "Strength": 5.0,
    },
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Emission`，对应 `ShaderNodeEmission` |
| `input_kwargs` | `Color`、`Strength` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Color` | Color | 发射光颜色 |
| `Strength` | Float | 发光强度；材质表面 1 通常呈现为不受光照影响的原色，更高值才明显照亮环境 |

**Output Sockets**：`Emission`（Shader）。材质中接 `MaterialOutput.inputs["Surface"]` 或 `MixShader`；灯光节点树中接 `LightOutput.inputs["Surface"]`。

发光材质是否能有效照亮场景取决于渲染器、采样和物体面积。资产 shader 负责提供合理 closure，不应在节点函数中修改全局灯光或 render 设置。

## `Nodes.PrincipledVolume`

**作用**：在一个节点中组合体积散射、吸收、发光和黑体辐射。

**创建方式**：

```python
volume = nw.new_node(
    Nodes.PrincipledVolume,
    input_kwargs={
        "Color": (0.7, 0.75, 0.8, 1.0),
        "Density": 0.2,
        "Anisotropy": 0.1,
    },
)
nw.new_node(
    Nodes.MaterialOutput,
    input_kwargs={"Volume": volume},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.PrincipledVolume`，对应 `ShaderNodeVolumePrincipled` |
| `input_kwargs` | 使用下表中的 Blender 4.2 socket 名称 |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Color` | Color | 体积散射颜色 |
| `Color Attribute` | String | volume grid 的颜色属性名；普通 mesh 容器留空 |
| `Density` | Float | 均匀密度或密度缩放；从小值开始，尺度越大视觉上越浓 |
| `Density Attribute` | String | volume grid 密度名，通常为 `density` |
| `Anisotropy` | Float | 0 为各向同性，正值偏前向散射，负值偏后向散射 |
| `Absorption Color` | Color | 吸收后的体积阴影色调 |
| `Emission Strength` | Float | 体积自发光强度 |
| `Emission Color` | Color | 体积自发光颜色 |
| `Blackbody Intensity` | Float | 黑体发光权重；烟火模拟常用 |
| `Blackbody Tint` | Color | 黑体颜色乘色 |
| `Temperature` | Float | 无 temperature grid 时使用的开尔文温度 |
| `Temperature Attribute` | String | volume grid 温度属性名，通常为 `temperature` |

**Output Sockets**：`Volume`（Shader），只连接 Material/World Output 的 `Volume`，不要接 Surface。

`Color Attribute`、`Density Attribute` 和 `Temperature Attribute` 是 OpenVDB/volume grid 名称，不是 Geometry Nodes 的普通 named attribute。室内单体资产很少需要体积；灯罩、半透明塑料和玻璃应先考虑表面 shader。

## `Nodes.PrincipledHairBSDF`

**作用**：为 hair curves/strands 创建物理毛发 shader；主要面向 Cycles。

**创建方式**：

```python
hair = nw.new_node(
    Nodes.PrincipledHairBSDF,
    input_kwargs={
        "Color": (0.04, 0.015, 0.006, 1.0),
        "Roughness": 0.3,
        "Radial Roughness": 0.35,
        "Random Roughness": 0.1,
    },
    attrs={"model": "CHIANG", "parametrization": "COLOR"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.PrincipledHairBSDF`，对应 `ShaderNodeBsdfHairPrincipled` |
| `input_kwargs` | 只设置当前 `model` + `parametrization` 启用的 socket |
| `attrs` | `model`：`CHIANG`/`HUANG`；`parametrization`：`COLOR`/`MELANIN`/`ABSORPTION` |

**Input Sockets**：由 `model` 和 `parametrization` 动态启用，只设置当前组合对应的输入。

### 颜色参数化

| `parametrization` | 启用的颜色输入 | 用途 |
| --- | --- | --- |
| `COLOR` | `Color` | 直接指定 strand RGB；最适合从已有材质颜色迁移 |
| `MELANIN` | `Melanin`、`Melanin Redness`、`Tint`、`Random Color` | 用色素浓度生成自然发色 |
| `ABSORPTION` | `Absorption Coefficient` | 直接提供吸收系数，适合物理数据驱动 |

### 共用输入

| Socket | 说明 |
| --- | --- |
| `Roughness` | 沿发丝方向的高光粗糙度 |
| `IOR` | 毛发折射率 |
| `Offset` | 鳞片倾斜导致的高光偏移 |
| `Random Roughness` | strand 间粗糙度变化 |
| `Random` | 随机源；不连接时使用 Hair Info 的 strand random |

### 模型专用输入

| `model` | 启用输入 | 说明 |
| --- | --- | --- |
| `CHIANG` | `Radial Roughness`、`Coat` | 分别控制径向高光粗糙度和外层高光 |
| `HUANG` | `Aspect Ratio`、`Reflection`、`Transmission`、`Secondary Reflection` | 支持椭圆截面，并分别控制主要散射分量 |

`Random Color` 只在 `MELANIN` 参数化下启用。不要向未启用的 socket 写值，否则代码会依赖 Blender 内部 socket 状态并难以迁移。

**Output Sockets**：`BSDF`（Shader），连接 `MaterialOutput.inputs["Surface"]`。

该节点不会创建毛发几何。只有地毯绒毛、织物纤维等明确需求时才考虑；普通布料表面应使用 Principled BSDF 的 sheen 和细尺度 normal/displacement。该低频接口仍由本页完整记录。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 把 Principled Volume 接到 `Surface` | 接 `MaterialOutput.inputs["Volume"]` |
| 把薄灯罩做成高密度 volume | 使用 Translucent/Principled Surface；volume 用于参与介质 |
| 对普通 mesh 使用 Hair BSDF | 先确认对象是 hair/curves，并采用 Cycles 支持的流程 |
| `parametrization="COLOR"` 时设置 `Melanin` | 只设置当前参数化启用的颜色输入 |
| 只提高 Emission Strength 便期待稳定照明 | 同步评估发光面积、采样和是否需要真实 Light object |
| 在资产 shader 中修改全局 volume/render 参数 | 资产只构建节点；场景和渲染配置交给 runner |

## 相关文档

- Principled 表面发光：`principled_bsdf_node.md`
- 表面透明、透光与 shader 混合：`surface_bsdf_nodes.md`
- Curves Info：`shader_input_nodes.md`
- Material/Light/World Output：`shader_world_output_nodes.md`
- Material API：`../../material_api/README.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/assets/lighting/indoor_lights.py`
- `infinigen/assets/materials/fluid/atmosphere_light_haze.py`
- `infinigen/assets/materials/fluid/smoke.py`
- `infinigen/assets/objects/creatures/util/hair.py`
- [Blender 4.2 Emission](https://docs.blender.org/manual/en/4.2/render/shader_nodes/shader/emission.html)
- [Blender 4.2 Principled Volume](https://docs.blender.org/manual/en/4.2/render/shader_nodes/shader/volume_principled.html)
- [Blender 4.2 Principled Hair BSDF](https://docs.blender.org/manual/en/4.2/render/shader_nodes/shader/hair_principled.html)
