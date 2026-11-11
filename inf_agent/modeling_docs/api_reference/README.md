# API Reference 路由

正常的资产生成任务不应从本目录开始。先按照生成 Skill 完成对象和建模方式路由，只有写到具体代码操作时才查询 API：

```bash
python -m inf_agent.cli query api --query "<精确符号或代码操作>"
```

`query api` 依次尝试完整源码符号/文档化接口、明确别名、自然语言操作路由，最后给出低置信度 token 相关候选。每个命中结果直接给出至多三份关联 API 叶子文档，不要求 Agent 再读取中间路由卡；维护规则见 [`operation_routes/README.md`](operation_routes/README.md)。

## 目录职责

| 目录 | 负责内容 | 不负责内容 |
| --- | --- | --- |
| `function_api/` | Infinigen Python 类、函数、对象与 mesh helper、modifier、变换和生命周期调用契约 | 选择资产形态、证明视觉质量 |
| `node_api/` | `NodeWrangler`、nodegroup、节点、socket、`attrs` 和版本兼容事实 | 决定是否应该采用 Geometry Nodes |
| `material_api/` | 具体材质类、材质候选池、shader function 及创建/赋值接口 | 决定资产整体造型 |
| `operation_routes/` | 无精确接口名时使用的自然语言操作路由元数据 | API 实现细节、建模 Pattern、完整示例 |

建模机制由 `modeling_patterns/` 负责；对象或原生 Factory 由 `asset_examples/objects/` 负责；材质视觉语义优先由 `asset_examples/materials/` 负责；执行、保存、渲染和导出由 runner 负责。

## 手动回退

需要补充上下文、查询元数据缺失或维护文档时，可按下表进入子目录：

| 当前需要 | 回退入口 |
| --- | --- |
| Python Factory、mesh/object、modifier、变换、材质赋值 | [`function_api/README.md`](function_api/README.md) |
| `NodeWrangler`、nodegroup、node socket 或 `bl_idname` | [`node_api/README.md`](node_api/README.md) |
| 具体材质类、语义候选池或简单 shader fallback | [`material_api/README.md`](material_api/README.md) |
| 输出模块和 runner 所有权 | `inf_agent/skills/in3d-generate-asset/references/runner_contract.md` |
| 已有原生对象实现 | `python -m inf_agent.cli query object --query "<对象>"` |

API 叶子文档记录固定仓库版本下的接口事实。索引生成器只扫描 `function_api/`、`material_api/` 和 `node_api/` 中非 README 的叶子文档；总览和操作路由不会参与符号关联。接口是否常用、是否允许 generated asset 直接调用，只影响路由优先级和所有权说明，不影响接口是否被文档保留：低频、runner 级、场景级、仿真级和兼容接口仍必须归入合适文档。

建议从当前操作所需的一至三份叶子文档开始，按需补充；这不是硬性阅读限制。
查询默认返回三项，`--limit` 可调整命中数；无需整份加载索引，维护或调试时可直接检查。维护文档时则必须保证三类接口没有因为整理、合并或职责迁移而丢失。

## 匹配依据

`match_type` 分别为 `exact_symbol`、`exact_documented_interface`、`alias`、
`operation_route` 和 `token_related`。操作路由另有 `route_match_type` 解释维护元数据的
命中方式。`why` 给出字段或别名依据。精确查询保持标识符整体匹配，忽略大小写，
不会将 `from_pydata` 拆成共享的 `from`。支持 `NodeWrangler.new_node`、
`infinigen.core.nodes.node_wrangler:NodeWrangler.new_node` 和完整点分名称。

置信度表示词法依据强度，不是适用性或代码正确性的概率：完整符号为 1，明确别名为
0.95（外部接口别名可规范化分隔符与下划线），token 相关为 0.5；操作路由依据维护短语为 0.8–1。即使命中也需核对真实参数和用途。
Blender 外部 API 以文档化入口返回，例如 `from_pydata` 指向
`bpy.types.Mesh.from_pydata`，只读对应文档；不要把外部接口传给仓库符号 reader。
