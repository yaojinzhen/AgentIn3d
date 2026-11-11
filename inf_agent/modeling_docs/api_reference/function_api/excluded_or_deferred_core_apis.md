# Core API 所有权与调用边界

本文档是 `infinigen/core` 跨模块接口的所有权路由表：它说明哪些能力属于单体静态资产代码，哪些属于场景、仿真、渲染、任务或导出层，以及遇到相关需求时应转向哪里。

它不是对 Infinigen 模块质量的评价，也不从 API 参考中删除任何接口。这里的“排除”仅表示 generated asset code 不应直接调用；“暂缓”表示需要独立的能力边界和验证契约。接口仍按其真实模块和所有权保留。

## 决策原则

静态单体资产代码应：

- 创建一个可复现的静态资产，主要几何位于 local coordinates。
- 通过 `AssetFactory` 生命周期返回 object 或 object hierarchy。
- 只负责资产内部的 mesh、Geometry Nodes、材质、局部变换和静态 parent/collection。
- 不控制相机、场景布局、全局渲染、任务调度、仿真编译或导出格式。

## 总览

| 模块 | 静态单体资产中的所有权 | 核心原因 | 替代入口 |
| --- | --- | --- | --- |
| `core/constraints/**` | 排除 | 场景关系表达、房间布局和求解器，不是单体建模 | 在 local space 建模；场景系统负责摆放 |
| `core/sim/**` | 排除 | 关节、运动学、物理材质和仿真格式导出 | 生成静态默认姿态；保留为未来 sim skill |
| `core/rendering/**` | 排除 | compositor、render pass、图像渲染和后处理属于 runner | 只赋材质，不调用 render |
| `core/placement/factory.py` | 纳入 | 单体资产的基础生命周期 | 见 `asset_factory_lifecycle.md` |
| `core/placement/camera*.py` | 排除 | 相机生成、轨迹、取景和可见性选择属于场景级职责 | runner 或场景生成框架 |
| `core/placement/placement.py` | 暂缓 | placeholder、collection populate 和批量实例摆放 | factory 只返回资产；调用方决定 world transform |
| `core/placement/instance_scatter.py` | 暂缓 | 面向表面/场景批量散布，不是资产主体结构 | 少量重复部件用 Geometry Nodes 显式实例化 |
| `core/placement/particles.py` | 排除 | 粒子系统配置与 bake 引入场景状态 | 静态 mesh/curve/instances |
| `core/placement/animation_policy.py`、`path_finding.py` | 排除 | 动画策略和路径规划 | 固定默认姿态 |
| `core/placement/detail.py` | 暂缓 | 自适应 remesh 与场景细节策略，成本和拓扑变化较大 | 明确的 modifier 或受控细分 |
| `core/placement/density.py`、`split_in_view.py` | 排除 | 依赖 tag、相机或场景可见性 | 资产内部显式 selection/attribute |
| `core/generator.py`、`core/execute_tasks.py` | 排除 | 项目任务编排、保存和渲染入口 | 外部 runner 调用 generated factory |
| `core/init.py` | 排除 | Blender、gin、设备和渲染环境初始化 | 运行环境统一配置 |
| `core/util/exporting.py` | 排除 | mesh/instance 序列化属于输出流水线 | 返回 Blender object，由 runner 导出 |
| `core/util/camera.py` | 排除 | 投影矩阵和视锥查询依赖相机 | 不在资产代码中判断屏幕可见性 |
| `core/util/pipeline.py` | 排除 | 随机阶段执行器属于项目流水线 | factory 内使用明确生命周期方法 |

## 场景约束与布局

### `core/constraints/**`

排除范围包括：

- `constraint_language` 中的 `Problem`、`scene`、`tagged`、`SupportedBy`、`Touching`、`CoPlanar`、距离和房间表达式。
- `evaluator` 与 `reasoning` 中的约束求值、domain 推理和 memo。
- `example_solver` 中的退火、move、房间图、楼层平面和 populate 流程。

这些 API 操作的是多个对象之间的关系与场景状态。把它们写入单个资产 factory 会让资产创建依赖房间、其他对象、BVH 或 solver stage，破坏独立生成和单元验证。

| 用户意图 | 静态单体资产中的处理 |
| --- | --- |
| “椅子放在桌旁” | 只生成椅子；位置关系交给场景编排器 |
| “柜子贴墙且不碰门” | 柜子以 local origin 为基准生成；碰撞/约束交给布局系统 |
| “台灯稳定地放在桌面” | 让资产最低点为 Z=0，并设计合理底座；不求解 `SupportedBy` |

不要为了复用几何工具而从 `core/constraints/.../util.py` 导入函数。单体 mesh 的 bbox、坐标和采样应优先查 `attributes_and_mesh_data.md`、`assets_object_mesh_helpers.md` 和 `math_random_sampling.md`。

## 仿真、关节与动画

### `core/sim/**`

排除范围包括：

- `kinematic_compiler.compile`、`KinematicNode`、`JointType` 和关节图构建。
- `spawn_simready` 与 joint metadata 检查/注入。
- `physics/**` 中的关节动力学和物理材质属性。
- `exporters/**` 中的 MJCF、URDF、USD builder 与导出函数。

静态单体资产只生成默认状态。例如柜门保持关闭、抽屉保持收回、轮子保持固定。可以用普通 object hierarchy 表达部件结构，但不要输出 joint parent/child socket、运动范围或仿真 metadata。仿真接口仍保留给具备独立契约的调用方。

`infinigen/assets` 中调用上述能力的 helper 也不因位于 `assets` 而自动允许。例如 `nodegroup_push_bar_handle` 输出关节相关结果，因此在 `reusable_component_helpers.md` 中明确排除。

### 动画与路径规划

`core/placement/animation_policy.py`、`camera_trajectories.py` 和 `path_finding.py` 依赖时间轴、场景 BVH、相机或其他对象。generated factory 不应插入 keyframe、改变 frame range 或寻找 world-space 路径。

## 相机、渲染与后处理

### 相机 API

以下能力由 runner 或场景层拥有：

- `core/placement/camera.py` 的 `spawn_camera`、`configure_cameras`、camera proposal 和可见性预处理。
- `core/placement/camera_trajectories.py` 的轨迹计算与动画。
- `core/util/camera.py` 的投影矩阵、screen projection 和 `points_inview`。

资产尺寸和细节不能根据当前相机动态改变，否则同一 seed 在不同预览环境中会得到不同资产。需要细节等级时使用 `asset_parameters`、`face_size` 或显式 factory 参数，而不是读取 active camera。`AssetFactory.spawn_asset` 在 `coarse=True` 时会直接报错；`coarse` 只供 runner 的 placeholder 流程使用。

### `core/rendering/**`

不要调用：

- `render_image`、`configure_compositor` 或 compositor output 配置。
- pass index、clay/flat shading、全局材质替换和 displacement mode 全局修改。
- EXR/depth/normal/segmentation 的加载、着色与后处理。

generated code 可以创建并赋予材质，但不应修改 world、render engine、view layer、compositor 或其他资产的材质。材质操作见 `surface_material_ops.md`，具体材质选择见 `../material_api/README.md`。

## Placement 接口归属

静态单体资产默认直接调用：

```python
from infinigen.core.placement.factory import AssetFactory, make_asset_collection
```

`AssetFactory` 管理 seed、`spawn_asset`、`finalize_assets` 和单体资产生命周期，详见 `asset_factory_lifecycle.md`。`make_asset_collection` 只在 factory/collection 复用场景中使用。

其余 placement 模块按以下方式处理：

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| `placement.py` | 暂缓 | `objects_to_grid` 可用于开发预览，但 `populate_*`、placeholder 和批量摆放不进入资产代码 |
| `instance_scatter.py` | 暂缓 | 未来可作为复杂资产表面散布能力；当前需单独验证密度、realize 和 seed 契约 |
| `detail.py` | 暂缓 | remesh 会改变拓扑和 attribute；只有明确需求与测试后才纳入 |
| `density.py` | 排除 | 面向 tag 驱动的 placement mask |
| `particles.py` | 排除 | 配置并 bake 粒子系统，副作用超出 factory |
| `split_in_view.py` | 排除 | 结果依赖相机和 world-space 可见性 |

在单体资产内部放置桌腿、按钮、层板等组成部分，不属于场景 placement。应使用固定 local transforms、Geometry Nodes instances 或 `object_join_parent_collection.md` 中的 parent/join 接口。

## 项目初始化、任务与导出

### 项目级入口

禁止 generated asset code 调用：

- `Generator`。
- `execute_tasks`、`render`、`save_meshes` 或 `main`。
- `configure_blender`、`configure_render_cycles`、设备选择、addon 安装和 gin 配置。

这些入口拥有整个 Blender 进程和任务目录。factory 在已配置环境中被调用，不应递归启动或重新配置项目流水线。

### 导出 API

`core/util/exporting.py` 的实例枚举、mesh 数据提取和 `save_obj_and_instances` 暂不进入 Function API。资产代码的输出契约是 Blender object/collection，而不是文件路径或外部格式。保存 `.blend`、OBJ、USD、URDF、MJCF 等由 runner 统一完成。

## 暂缓接口的启用条件

“暂缓”模块需要满足以下条件后才可升级为 API：

1. 有明确的非静态单体需求和能力边界。
2. 拆出不依赖相机、场景全局状态或外部文件的最小接口。
3. 记录 seed、Blender context、attribute 保留和性能契约。
4. 提供独立测试资产，验证重复执行和清理行为。
5. 更新 Function API 路由和 generated-code runner 边界。

## Agent 决策表

| 代码意图 | 决策 |
| --- | --- |
| 创建/修改单个资产的 mesh、nodegroup、材质 | 允许；路由到对应 Function/Node/Material API |
| 在资产内部复制和摆放组成部件 | 允许；使用 local transforms 或 Geometry Nodes |
| 返回多个静态子 object 并建立 parent | 允许；见 `object_join_parent_collection.md` |
| 查询房间、墙、地面、其他 factory 或场景 BVH | 排除 |
| 创建相机、灯光环境、渲染 pass 或输出图像 | 排除 |
| 添加 keyframe、关节、刚体、粒子 bake 或运动学 metadata | 排除 |
| 保存文件、导出格式、启动任务或配置 Blender | 排除 |
| 根据 active camera 改变资产几何 | 排除 |
| 使用 `asset_parameters`、`face_size` 或显式 factory 参数控制资产细节 | 允许 |
| 在 generated asset code 中设置 `coarse=True` 后调用 `spawn_asset` | 排除；`coarse` 只供 runner 的 placeholder 流程使用 |

## 发现排除依赖时的回退顺序

1. 判断需求是否真属于资产内部静态几何。
2. 若属于，改写为 primitive、modifier、Geometry Nodes 或 local transform。
3. 若涉及对象间关系，只输出便于摆放的 origin、尺度和静态结构。
4. 若涉及交互，只输出合理默认姿态，不伪造 joint metadata。
5. 若核心需求必须依赖排除模块，停止生成该部分并把需求路由给未来的场景、仿真或 runner skill。
