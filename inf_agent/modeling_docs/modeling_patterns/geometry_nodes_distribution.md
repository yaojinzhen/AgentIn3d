---
id: geometry-nodes-distribution
domain: pattern
intent: 使用 Geometry Nodes 或实例化构造受控的重复、分支和场驱动分布
aliases: ["geometry nodes", "repetition", "distribution", "array", "veins", "ribs", "几何节点", "重复结构", "分布"]
use_when: "数量、间距、表面位置、遮罩、分支层级或场变化共同驱动多个相关元素。"
avoid_when: "只有一个部件，或少量固定重复用直接网格、曲线和 Python 实例更清晰。"
source_symbols: ["infinigen.core.nodes.node_wrangler:NodeWrangler", "bpy.types.GeometryNodeTree"]
related_patterns: ["thin-organic-surface", "rigid-assembly"]
summary: "将源几何和分布规则分开，以有界参数控制数量、朝向、缩放和遮罩，并验证实际求值结果。"
---

# Geometry Nodes 分布与重复

Geometry Nodes 是分布机制，不是质量标签。先定义源几何，再定义点、曲线、表面坐标或遮罩驱动的
分布规则。对数量较少且固定的部件，直接 Python 实例化通常更容易检查。

编码时查询 API 的 Geometry Nodes 意图卡，并只读取
`../api_reference/node_api/nodegroup_authoring.md` 与当前节点族所需的一个叶文档。

## 适用结构

- 肋条、齿、菌褶、缝线、散热片或通风槽；
- 由主脉或中心曲线驱动的叶脉与分支；
- 需要继承表面局部朝向、遮罩和尺度的实例；
- 需要暴露数量、间距、方向、渐变、种子或覆盖范围的重复细节。

实例数量必须有上限；仅在导出或下游修改器需要时 realize instances。随机参数必须固定种子并限制
幅度，不能删除必要特征或制造大面积重叠。节点和 socket 名称必须以仓库使用的 Blender 版本为准。

## 方法专属验证

检查 evaluated mesh 的数量、覆盖范围、朝向、缩放、裁剪、端点和性能，而不是只检查是否存在节点组。
空输出优先检查几何流、选择遮罩、组输入输出和暴露参数。重复结构破坏主轮廓时，应修改分布规则或
降低作用范围，而不是继续增加主体细分。
