---
id: troubleshoot-factory-code
domain: troubleshoot
intent: 诊断语法、导入、AssetFactory 生命周期或禁止操作错误
aliases: ["SourceContractError", "syntax error", "factory missing", "import error", "AssetFactory", "代码契约错误"]
use_when: "preflight 拒绝 asset.py，或 traceback 指向导入、类定义、create_asset 等代码契约边界。"
avoid_when: "代码已经成功执行，失败属于视觉几何、材质或装配质量。"
source_symbols: ["inf_agent/skills/in3d-generate-asset/references/runner_contract.md"]
related_patterns: []
summary: "在分配新的 Blender attempt 前，只修复报告指出的语法、符号、类、生命周期或副作用错误。"
---

# Factory 代码失败

以报告的准确行号为起点，检查唯一直接 `AssetFactory` 子类、definition-only 模块顶层、
`create_asset`、可见根对象返回值、真实存在的 import，以及 runner 所有权之外的文件、动态
导入或场景操作。

不猜测 API 拼写；通过 `query api` 查准确符号。preflight 失败不应消耗 attempt，只修复代码
契约问题，不同时进行未经证据支持的视觉重写。
