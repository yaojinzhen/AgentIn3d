# 失败诊断路由

本目录只保存资产生成失败后的按需诊断卡。正常建模不预读这些文档；先查看 `preview` 或
`finalize` 的真实摘要、日志和视觉证据，再执行：

```bash
python -m inf_agent.cli query troubleshoot --query "<错误、状态或失败域>"
```

一次只处理最高优先级失败域：

| 证据 | 诊断卡 |
| --- | --- |
| `environment_failure`、缺少 `bpy`、native crash、外部超时 | `environment.md` |
| `SourceContractError`、语法/导入/Factory 生命周期错误 | `factory_code.md` |
| 空 mesh、异常 bounds、严重拓扑或错误轮廓 | `geometry.md` |
| 附件悬空、错误锚点、缺少连接件或严重穿插 | `assembly.md` |
| 未分配材质、颜色/粗糙度/映射尺度错误 | `material.md` |
| 私有 helper、注册、配置或场景依赖导致复用失败 | `native_reuse.md` |
| 可复现的几何量、内存、渲染或预览性能瓶颈 | `performance.md` |
| 相同候选不可复现，或随机性破坏必要特征 | `randomness.md` |

环境失败不得消耗资产修复预算。查询结果为空时保留原始证据，不猜测错误类型，也不通过
简化资产或降低质量门禁制造“通过”。
