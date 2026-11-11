# 1.1 使用指南

产品版本为 `1.1`；工作区和运行输入使用 `schema_version="2"`。旧协议工作区和生成结果不提供迁移。

## 环境与入口

按[仓库安装说明](../../README.md)准备 Python 3.11、bpy 4.2.0 和根 `.venv`，从仓库根目录运行。

| 平台 | 固定解释器 |
| --- | --- |
| Windows | `<repo>/.venv/Scripts/python.exe` |
| Linux/macOS | `<repo>/.venv/bin/python` |

下文示例采用 Linux/macOS 写法；Windows PowerShell 将 `./.venv/bin/python` 替换为
`& .\.venv\Scripts\python.exe`。子进程沿用 `sys.executable`。
Skill 先解析目录链接的真实位置，再定位所属仓库；不从当前目录猜测另一份检出。
环境不存在时先按根安装说明准备，不回退到 PATH、Conda 或其他 Python。
虚拟环境不能跨系统复用，移动仓库后应重建并检查 Skill 链接。

```bash
./.venv/bin/python -m inf_agent.cli --version
./.venv/bin/python -m inf_agent.cli --help
./.venv/bin/python -m inf_agent.cli doctor
```

doctor 显式检查最小建模、BLEND 保存重开和 GLB 导出重导入，不是创建工作区的前置步骤。

## 创建与编辑工作区

```bash
./.venv/bin/python -m inf_agent.cli start --asset-id apple --prompt "生成一个红苹果"
./.venv/bin/python -m inf_agent.cli start --workspace <新目录> --prompt-file <文本文件> --image <参考图>
```

可选 --width、--depth、--height 表示米制最终世界坐标轴尺寸；可重复 --forbid 记录禁止内容。
已有目录不覆盖，需要继续时编辑其中的输入和源码。

```text
<workspace>/
  request.json       # 原始需求、尺寸、禁止内容、参考图、本地依赖
  reference.*        # 可选参考图
  asset.py           # Agent 编写的 Factory
  design.md          # 可选技术设计
  design.json        # 可选方向、比例、部件/连接/开口/区域/特写约束
  runs/<run-id>/     # 当次输入快照、产物与诊断
```

保留原始需求文字，将尺寸推导和实现选择写入技术设计。输入可修订；已有运行保留当次快照。
简单单体不必注册语义部件。需要测量具体装配、开口或材质区域时，参见
[设计字段](../skills/in3d-generate-asset/references/design_contracts.md)和
[装配与开口](../skills/in3d-generate-asset/references/geometry_and_assembly.md)。

Factory 可直接或间接继承 AssetFactory。默认选择唯一的本地叶子子类；多个可选类或导入原生类时，
用 --factory <ClassName> 指定。返回值须为包含实际可见 mesh 的已链接 Blender Object。

### 本地依赖与资源

在 request.json 的可选 local_dependencies 中声明工作区相对文件或目录，例如：

```json
{"local_dependencies": ["helper.py", "local_pkg", "textures", "resources"]}
```

执行时复制主源码、声明的依赖、参考图和已有 design.md，依赖保留相对结构，忽略 Python 缓存。
普通导入、包导入和延迟导入均使用当次快照，不回退读取未声明的实时 helper。
资源使用 `Path(__file__).parent / "textures" / "skin.png"`；进程 cwd 始终是仓库根目录。
Infinigen、Blender、第三方库及代码主动访问的外部路径没有被冻结。

## 查询知识与读取源码

```bash
./.venv/bin/python -m inf_agent.cli query object --query "apple"
./.venv/bin/python -m inf_agent.cli query pattern --query "rounded organic mass"
./.venv/bin/python -m inf_agent.cli query api --query "NodeWrangler"
./.venv/bin/python -m inf_agent.cli query material --query "fruit skin"
./.venv/bin/python -m inf_agent.cli read --document asset_examples/objects/apple_fruit.md
./.venv/bin/python -m inf_agent.cli read --symbol infinigen.core.placement.factory:AssetFactory
./.venv/bin/python -m inf_agent.cli lint --source <workspace>/asset.py
```

query 默认返回至多三项，可用 --limit <正整数> 调整。按需查询和阅读是上下文建议，不是阅读资格限制。
普通文件读取同样适用；lint 是可选语法与已知 API 诊断。

将 document_path 或 documents[] 原样传给 read --document，将 source_symbols[] 传给 read --symbol。
章节提示在 document_heading / document_references[].heading 中。source_references[] 区分源码符号、
目录、模块、源码位置和外部 API；只有 source_symbols[] 承诺可直接交给符号 reader。
匹配类型和置信度说明见 [API 总览](../modeling_docs/api_reference/README.md)。

## 预览、修复与导出

```bash
./.venv/bin/python -m inf_agent.cli preview --workspace <workspace> --seed 0 --resolution 512x512 --samples 32
./.venv/bin/python -m inf_agent.cli export --workspace <workspace> --texture-resolution 2048 --bake-samples 4
./.venv/bin/python -m inf_agent.cli export --workspace <workspace> --no-render
./.venv/bin/python -m inf_agent.cli validate --run <run-directory>
./.venv/bin/python -m inf_agent.cli status --workspace <workspace>
```

preview 与 export 都执行当前源码并创建新运行。预览保存 BLEND 和请求的多视图；导出还生成含材质的 GLB，
详见 [GLB 导出](GLB_EXPORT.md)。失败结果与日志保留，可编辑设计或源码后重新运行。

每个工作区默认最多分配 **20 次** preview/export，失败和中断分配也计数，最终导出占一次。
达到上限时在启动 Blender 前返回退出码 2，不自动删旧结果或重试。status.run_budget 给出默认额度参考。
用户希望继续更多运行时，可在 --limits JSON 中显式设置 max_runs，例如 {"max_runs": 30}。
status 与 validate 不占次数；它们也不会重新构建源码。

查看实际全局图、反向图及相关局部图，再判断轮廓、尺寸、特征、连接和材质。还应重开 GLB 查看导出外观；
程序化 BLEND 的图片不能替代导出验证。程序 visual_status 固定为 NOT_CHECKED；无法看图时说明视觉未验证。
结果字段、文件职责及可执行诊断示例统一见 [输出格式](OUTPUT_FORMAT.md)。

validate 重新解析当前文件并启动独立 Blender 重开，设计检查仍使用已存几何指标。
模型或源码变化后应重新 preview/export。status 返回最新分配运行；若中断且没有 result.json，latest_result 为 null。

## 资源与故障处理

用 --limits <json> 覆盖已实施的资源阈值，例如：

```json
{"max_runs": 20, "max_build_seconds": 600.0, "max_wall_seconds": 2400, "max_evaluated_vertices": 3000000}
```

阈值须为有限正数，计数为整数。运行次数按工作区计；时间、渲染参数、对象/顶点/面/材质数量和输出体积按单次执行计。
不会限制整个项目累计时间或磁盘占用。

先看 result.error 的原始异常，再区分进程、构建、文件和客观测量问题。
process.log / process_status.json 记录启动和超时，run.log 记录构建，reopen.log / artifact_reopen.json 记录当前文件重开。
原始子进程报告为 validation.json，几何与产物诊断在 objective_validation.json。

```bash
./.venv/bin/python -m inf_agent.cli query troubleshoot --query "<实际错误>"
```

退出码：成功为 0，执行或客观检查失败为 1，已知输入/配置错误或运行额度用尽为 2。

## 执行边界

资产 Python 以当前用户的文件、网络和环境权限运行；框架没有内置沙箱或权限隔离，应执行可信代码。
Factory、输入与输出检查不构成安全边界。进程监控在超时或体积超限时终止当前子进程，但不保证清理资产代码主动派生的进程。
峰值内存供诊断使用，不是硬隔离；系统级 CPU、内存、进程或文件访问限制由外部环境提供。

start 在同父目录的 staging 准备完整输入，发布时不覆盖目标。复制回退路径只回滚本次创建的文件，
失败保留完整 staging 并给出恢复路径，不递归清理来源不明的文件。
JSON 使用同目录临时文件、flush、fsync、原子替换和 Windows 短暂占用重试。
已有工作区、失败证据和生成结果不自动清理；避免同时编辑同一工作区输入或验证同一运行。

项目说明与维护入口见 [Agent README](../README.md)。Skill 的目标目录按所用 Agent 的规则确认，并通过目录链接注册。
