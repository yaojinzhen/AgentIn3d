# 机器索引

本目录保存 Python 查询器使用的可重建机器数据；日常建模优先读取命中的知识文档。
`api_index.json` 包含 Infinigen 源码符号、文档化接口、签名、角色、源码位置与 API 叶子文档映射。

维护/调试时可直接检查 JSON；修改源码或叶子文档后运行生成器重建，不手工维护生成结果。日常查询使用：

从仓库根目录使用根 `.venv`，Windows PowerShell 将下文的 `./.venv/bin/python`
替换为 `& .\.venv\Scripts\python.exe`；约定见[使用指南](../../docs/USER_GUIDE.md#环境与入口)。

```bash
./.venv/bin/python -m inf_agent.cli query <domain> --query "<查询内容>"
```

`domain` 为 `object`、`pattern`、`api`、`material` 或 `troubleshoot`。默认至多返回 3 项，可用 `--limit` 指定任意正整数；
统一 CLI 没有固定 8 KiB 输出截断。独立 `./.venv/bin/python -m inf_agent.indexing.query api` 工具
另有 `--max-chars` 字符预算（默认 12000 字符）和 `truncated` 字段，不能混同为 CLI 限制。

## 当前路由

| 查询域 | 文档来源 |
| --- | --- |
| `object` | `asset_examples/objects/` |
| `pattern` | `modeling_patterns/` |
| `api` | 完整符号/文档化接口、明确别名优先；其次使用 `api_reference/operation_routes/` 直达 API 叶子文档 |
| `material` | `asset_examples/materials/` |
| `troubleshoot` | `troubleshooting/` |

精确对象未命中时，`next_queries` 引导 Agent 按主形态查询 Pattern。未知静态单体对象仍可继续
建模，不得因没有对象卡而拒绝，也不得强制映射到单一资产分类；应组合结构特征、材质语义和
场景属性作出建模决策。

## 生成与检查

在仓库根目录执行：

```bash
./.venv/bin/python -m inf_agent.tools.generate_indexes
./.venv/bin/python -m inf_agent.tools.generate_indexes --check
```

生成器只使用 Python 标准库读取源码和 Markdown。`api_index.json` 的源码输入包括
`infinigen/assets/**/*.py` 和 `infinigen/core/**/*.py`；文档输入严格限制为 `function_api/`、
`material_api/`、`node_api/` 下的非 README 叶子文档。API 总览、操作路由和其他文档不参与
符号关联。

索引是可以重建的机器产物。上下文控制依靠受限查询、精确叶文档和局部源码片段，而不是压缩
JSON 或把完整索引放入模型上下文。


源码关联按标题中的接口所有权、所属类别和源码引用优先排序，再考虑正文提及。
一级标题中的反引号接口也参与关联，例如 NodeWrangler 的专属使用文档。
文档化 `bpy.types.*` 接口生成去掉 bpy.types 前缀及末级方法名的 aliases；
查询按完整别名匹配（分隔符和下划线可规范化为空格），不依赖共享 token。
匹配类型与置信度见[API 检索说明](../api_reference/README.md)。
