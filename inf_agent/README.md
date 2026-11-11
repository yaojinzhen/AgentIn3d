# Infinigen Agent 1.1

根据文字、单主体参考图或二者组合，编写 Infinigen / Blender 程序化代码，生成静态单体三维资产。
Agent 负责造型、材质和图像检查；执行服务负责 Factory 生命周期、多视图、几何诊断和 BLEND/GLB 输出。

版本：**1.1**。工作区与运行输入协议：`schema_version="2"`。

## 快速开始

按仓库根目录的[安装说明](../README.md)准备 Python 3.11、bpy 4.2.0 和根 `.venv`，从仓库根目录运行。
下文采用 Linux/macOS 路径；Windows PowerShell 将 `./.venv/bin/python` 替换为
`& .\.venv\Scripts\python.exe`。解释器约定见[使用指南](docs/USER_GUIDE.md#环境与入口)。

```bash
./.venv/bin/python -m inf_agent.cli --version
./.venv/bin/python -m inf_agent.cli start --asset-id apple --prompt "生成一个成熟的红苹果"
./.venv/bin/python -m inf_agent.cli query object --query "apple"
./.venv/bin/python -m inf_agent.cli read --document asset_examples/objects/apple_fruit.md
```

Agent 根据需求编写 `inf_agent/outputs/apple/asset.py`，然后预览、查看图片、修模和导出：

```bash
./.venv/bin/python -m inf_agent.cli preview --workspace inf_agent/outputs/apple
./.venv/bin/python -m inf_agent.cli export --workspace inf_agent/outputs/apple
./.venv/bin/python -m inf_agent.cli status --workspace inf_agent/outputs/apple
./.venv/bin/python -m inf_agent.cli validate --run <命令返回的运行目录>
```

每个工作区默认最多分配 20 次 preview/export，失败也计数；status/validate 不计数。
GLB 自动转换支持的程序化材质并内嵌贴图，原始 BLEND 保留可编辑节点。
`execution_success`、`objective_success` 分别表示执行与客观检查；视觉是否符合需求需查看实际图片。

## Agent Skills

- `in3d-generate-asset`：生成模型或修改几何、材质。
- `in3d-run-asset`：执行、导出、验证或诊断已有工作区。

按所用 Agent 的规则，将两个 Skill 目录通过目录链接放入目标 Agent 的 Skill 搜索目录。
目标路径由用户确认，可手动操作或交由 Agent 完成。链接应指向本项目源码目录，供 Skill 解析根 `.venv`。

## 文档

[文档索引](docs/README.md) · [使用指南](docs/USER_GUIDE.md) · [输出格式](docs/OUTPUT_FORMAT.md) ·
[GLB 导出](docs/GLB_EXPORT.md) · [1.1 发布说明](docs/RELEASE_NOTES.md)

长期建模方法、对象参考、API、节点、材质和故障知识位于 [modeling_docs](modeling_docs/README.md)。

执行、装配、输入管理、知识检索分别由 execution/、geometry/、workspace/、indexing/ 和 knowledge/ 维护；
skills/ 保存任务指引，tools/ 与 test/ 保存维护工具和回归。outputs/ 是本地生成结果，不属于发布源码。

## 维护检查

```bash
./.venv/bin/python -B -m inf_agent.tools.check
```

该命令检查代码编译、Agent 回归、知识索引与 Markdown 链接。修改知识文档后，通过
`./.venv/bin/python -B -m inf_agent.tools.generate_indexes` 更新索引。

来源与许可见[根 README](../README.md#来源与许可)。
