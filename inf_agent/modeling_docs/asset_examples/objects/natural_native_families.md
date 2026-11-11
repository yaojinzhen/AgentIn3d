---
id: natural-native-families
domain: object
intent: 仙人掌、珊瑚、树木、小型植物、软体动物和水下对象的原生路线索引
aliases: ["cactus", "coral", "tree", "bush", "fern", "succulent", "palm tree", "seaweed", "urchin", "mollusk", "nautilus", "仙人掌", "珊瑚", "树木", "灌木", "蕨类", "多肉植物", "棕榈树", "海草", "海胆", "软体动物", "鹦鹉螺"]
use_when: "用户请求可独立检查的静态自然单体，并且 Infinigen 中存在对应形态 Factory。"
avoid_when: "目标是云、地表覆盖、植物群落、鱼群，或依赖 rig、动画、boid 和生长仿真的场景能力。"
source_symbols: ["infinigen/assets/objects/cactus", "infinigen/assets/objects/corals", "infinigen/assets/objects/trees", "infinigen/assets/objects/small_plants", "infinigen/assets/objects/tropic_plants", "infinigen/assets/objects/mollusk", "infinigen/assets/objects/underwater"]
related_patterns: ["curve-sweep", "geometry-nodes-distribution", "custom-mesh-loft"]
summary: "先定位准确物种或形态 Factory，再只读取其直接依赖；群落、rig、仿真和场景散布不进入静态单体代码。"
---

# 其他自然单体原生路线

| 对象族 | 代表入口 | 使用边界 |
| --- | --- | --- |
| 仙人掌 | `CactusFactory` 及柱状、球状、掌状子类 | 可复用基础形体与刺分布，避免把重网格流程整段复制 |
| 珊瑚 | `CoralFactory` 及形态子类 | 先选与目标轮廓一致的生长或放样路线 |
| 树木/灌木 | `TreeFactory`、`GenericTreeFactory`、`BushFactory` | 只在静态单株可控时使用，注意多层实例成本 |
| 小型植物 | `FernFactory`、`SnakePlantFactory`、`SucculentFactory` | 叶片 Factory 与植株级装配分层读取 |
| 热带植物 | `PalmTreeFactory`、`CoconutTreeFactory`、`PlantBananaTreeFactory` | 保留长叶、树干分节和冠层关系 |
| 软体动物 | `MolluskFactory`、`NautilusFactory` | 壳体与软体部件分别选方法，不引入动画 |
| 水下单体 | `SeaweedFactory`、`UrchinFactory` | 只生成曲线海草或径向尖刺单体，不扩展为海底场景 |

水果、阔叶、蘑菇和岩石已有独立对象路由，应优先使用更精确的文档。云、鱼群、附着物散布和
带 rig 的生物不是本路由的 fallback；未命中准确 Factory 时继续查询主体形态 Pattern。
