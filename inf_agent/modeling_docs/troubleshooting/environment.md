---
id: troubleshoot-environment
domain: troubleshoot
intent: 诊断 Blender、Python、依赖、超时或原生进程导致的环境失败
aliases: ["environment_failure", "bpy missing", "timeout", "native crash", "环境错误", "超时"]
use_when: "preview 将失败分类为 environment/framework，或 runner 在没有资产代码证据时退出。"
avoid_when: "traceback 明确指向 asset.py，或资产客观验证失败。"
source_symbols: []
related_patterns: []
summary: "保留日志并检查环境和 runner 状态，不使用资产修复预算重写有效几何。"
---

# 环境与 runner 失败

先读取受限摘要和 `run.log`。缺少 `bpy`、依赖导入失败、runner 启动失败、没有
`asset.py` traceback 的 native crash，以及几何/导出已经成功后的外部超时，均属于环境
或框架证据。

保留 system attempt，检查所属仓库根 `.venv` 的 Python、bpy 和依赖状态；Windows 为
`.venv/Scripts/python.exe`，Linux/macOS 为 `.venv/bin/python`。Skill 应先解析目录链接的真实位置，
工作目录保持仓库根目录；子进程沿用 `sys.executable`。解释器缺失时指向根 README 安装说明，
不切换到 PATH、Conda 或其他检出，不要求安装 uv 才能运行 Agent。只在环境状态改变后重试。
不得为了把环境失败变成资产失败而简化模型代码，也不得扣减三个资产候选的修复预算。
