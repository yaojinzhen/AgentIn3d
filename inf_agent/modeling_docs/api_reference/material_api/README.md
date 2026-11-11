# Material API 路由

本目录记录具体材质类、材质候选池、shader function 以及创建、生成、应用和赋值接口。先用 `query material` 选择视觉语义，写到具体调用时再用 `query api` 查询精确材质类或函数。

## 文档类型

| 类型 | 文档 | 职责 |
| --- | --- | --- |
| 语义候选池接口 | `material_assignments.md` | 候选池变量、权重、采样协议、别名关系和源码缺陷 |
| 硬表面生成器 | `indoor_hard_surface_materials.md` | 金属、木材、塑料、橡胶、陶瓷、石材和铺装类/函数 |
| 软材质生成器 | `fabric_and_soft_materials.md` | 织物、针织、皮革、绒面、地毯和图案类/函数 |
| 透明与发光生成器 | `glass_screen_emissive_materials.md` | 玻璃、镜面、屏幕、透光塑料、灯罩和 emission 类/函数 |
| 后处理效果 | `wear_tear_materials.md` | `EdgeWear`、`Scratches` 及其 geometry/shader 调用契约 |
| 受控 fallback | `fallback_principled_materials.md` | 原生材质不可用时的 NodeWrangler/纯 `bpy` 最小材质接口 |

需要手动回退时，建议先按当前材质操作读取一份叶子文档，再按需补充：

| 材质操作 | 叶子文档 |
| --- | --- |
| 按部件语义加权选择材质 | `material_assignments.md` |
| 金属、木材、塑料、陶瓷和石材 | `indoor_hard_surface_materials.md` |
| 织物、针织、天鹅绒、皮革和地毯 | `fabric_and_soft_materials.md` |
| 玻璃、显示屏、镜面、镜片和发光表面 | `glass_screen_emissive_materials.md` |
| 划痕、崩边、污渍和磨损 | `wear_tear_materials.md` |
| 已验证的简单 Principled fallback | `fallback_principled_materials.md` |

本目录负责材质接口事实，不负责资产形态。各叶子文档中的“接口索引”只帮助从已确定的材质语义定位类或函数，不替代视觉决策。材质的视觉意图、尺度、分层和预览判断由 `asset_examples/materials/`，特别是 [`material_design_principles.md`](../../asset_examples/materials/material_design_principles.md) 负责。水果和叶片等与私有坐标强耦合的自然材质，可以由对应对象卡给出精确源码入口。

不要把“能创建某个材质”当作“该材质适合当前资产”的证据，也不要在一个任务中遍历完整材质目录。不得因材质类低频、存在缺陷或当前对象不使用而删除接口；应保留其签名并注明风险、调用所有权或 fallback。
