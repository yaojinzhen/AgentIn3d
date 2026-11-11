# 产物与结果格式

本页维护1.1 的文件职责与诊断路径，供 CLI、知识入口和两份 Skill 共用。
工作区输入及命令参数见[使用指南](USER_GUIDE.md)。每次 preview/export 分配独立运行目录；
失败也保留目录，早期中断时下述文件可能尚未生成。validate 重检指定运行并更新结果，
不会构建当前源码，也不会重新测量完整设计几何。

## 文件职责

| 文件 | 内容与读取时机 |
| --- | --- |
| `input/config.json`、`input/source/` | 当次配置、源码及显式本地依赖快照；reference 和 design.md 也按需保存 |
| `scene.blend`、`asset.glb` | 实际三维产物；GLB 仅 export 请求；路径存在不代表验证通过 |
| `previews/*.png` | 默认五个全局视图、按需 bottom、部件特写与 visible/potential masks；`--no-render` 不请求图片 |
| `validation.json` | 原始建模子进程报告，success/errors/error.type/message；没有 layers，不由父进程改写 |
| `metadata.json` | 实测资产指标及 metadata.error；用于后续存量设计检查 |
| `process_status.json` | 父进程记录的退出码、启动/超时状态 |
| `result.json` | 面向调用者的结果摘要、实际产物路径及故障域 |
| `objective_validation.json` | 分层客观检查，见下表 |
| `artifact_reopen.json`、`reopen.log` | 独立 Blender 子进程对当前请求 BLEND/GLB 的重开证据及日志 |
| `process.log`、`run.log` | 建模子进程 stdout/stderr、Factory 构建日志 |
| `resource_budget.json` | 当前执行的资源策略与使用情况 |
| `material_export.json`、`textures/*.png` | export 的材质转换模式/通道/设置/文件验证及烘焙图；GLB 同时内嵌图像，无需依赖旁路 PNG |

## 结果字段

preview/export/validate 的 CLI JSON 对应 result.json，失败运行也有可诊断的实际产物。

| 字段 | 含义 |
| --- | --- |
| `execution_success` | 构建与请求的渲染、保存、导出是否完成 |
| `objective_success` | 执行、客观几何/设计和请求产物检查是否通过 |
| `visual_status` | `NOT_CHECKED`；程序没有通用视觉相似度结论，需查看实际图片 |
| `artifacts`、`previews` | 实际存在的文件路径；不能单独证明质量 |
| `error` | 有效原始执行异常的 type/message；无原始报告时合成进程/报告错误；客观失败可为 null |
| `process` | 父进程独立退出/超时信息 |
| `execution_report_status` | 原始子进程报告 `VALID` / `MISSING` / `INVALID` |
| `failure_domains` | 如 construction、assembly、artifacts、environment、process，用于选择修复方向 |
| `errors`、`warnings` | 具体客观失败及诊断建议 |

status 返回 `latest_run` 和 `latest_result`，含义是最新分配的运行；最新运行中断且没有
result.json 时 latest_result 为 null。它不回退到更早的已完成结果。
status 的 `run_budget` 包含 `default_limit=20`、`used`、`remaining_at_default`；它表示默认额度参考，
每次执行的显式 max_runs 覆盖保存在 input/config.json 的 limits。失败分配也计数；validate/status 不计数。
退出码：成功 0，执行或客观检查失败 1，已知输入/配置或运行额度用尽为 2。

## 客观诊断路径

以下路径全部位于 objective_validation.json：

| 路径 | 内容 |
| --- | --- |
| `layers.execution_health` | 运行健康 |
| `layers.objective_asset_health.explicit_dimensions` | 各尺寸 expected_m、observed_m、relative_error、tolerance、passed；允许相对误差 15% |
| `layers.objective_asset_health` | bbox、拓扑、材质、比例、特写和连通性 |
| `layers.geometry_and_assembly` | 实例身份、部件数量、连接、穿插、开口与语义材质区域 |
| `layers.artifact_validation` | expected_outputs、files、files_usable、focus_evidence、blender_reopen、errors |
| `layers.visual_fidelity` | 保留 `NOT_CHECKED`，不代表视觉通过 |

validate 的 `measurement_source=stored_run_metadata` 表示设计检查使用已存指标；
`artifact_measurement_source=current_files_and_fresh_runtime_reopen` 表示当前文件重新检查。
GLB 静态 parsed、semantic_valid、materials_valid 与 Blender reopened 分开记录；
纹理需为可解码的内嵌 PNG/JPEG，材质 texture 索引与对应 UV 集必须有效；常量 PBR 不强制贴图。
预览图片必须完整解码且尺寸正确，
visible/potential mask 必须有目标像素且满足包含关系。不请求渲染时图片为 NOT_REQUESTED。
文件、mask 或重开失败应先诊断产物和环境，不据此盲目修改几何。

## 可执行诊断读取示例

将以下代码保存为 read_diagnostics.py，使用建模解释器运行
`./.venv/bin/python read_diagnostics.py <run-directory>`，Windows PowerShell 使用
`& .\.venv\Scripts\python.exe read_diagnostics.py <run-directory>`。该示例也由真实 Blender 端到端回归执行。

```python
import json
import sys
from pathlib import Path


def read_diagnostics(run):
    run = Path(run)
    result = json.loads((run / "result.json").read_text(encoding="utf-8"))
    report = json.loads((run / "objective_validation.json").read_text(encoding="utf-8"))
    layers = report["layers"]
    return {
        "execution_success": result["execution_success"],
        "objective_success": result["objective_success"],
        "error": result["error"],
        "process": result["process"],
        "dimensions": layers["objective_asset_health"]["explicit_dimensions"],
        "assembly_passed": layers["geometry_and_assembly"]["passed"],
        "files_usable": layers["artifact_validation"]["files_usable"],
        "visual_status": result["visual_status"],
    }


if __name__ == "__main__":
    print(json.dumps(read_diagnostics(sys.argv[1]), ensure_ascii=False, indent=2))
```

例如源模型宽度 0.5 米但 request 要求 1 米时，execution_success 可以为 true，
objective_success 为 false；dimensions.width 显示实测偏差。修正源码后重新 preview/export，
而不是修改旧运行快照或把 validate 当成重建。
