---
id: troubleshoot-native-source-quirks
domain: troubleshoot
intent: 诊断原生资产源码中的占位分支、未使用参数、私有 helper 和版本性实现缺陷
aliases: ["source quirk", "unused parameter", "placeholder branch", "native source bug", "源码陷阱", "未使用参数", "占位分支", "原生源码缺陷"]
use_when: "原生 Factory 可以定位，但请求参数不生效、返回对象异常、材质缺失或复制局部代码后行为与预期不符。"
avoid_when: "完整原生 Factory 已稳定生成正确结果，或失败属于环境、导入、随机性和普通建模错误。"
source_symbols: []
related_patterns: []
summary: "把原生源码视为需要验证的实现而非绝对契约；核对签名、参数消费、返回路径、材质应用和私有依赖后再复用。"
---

# 原生源码版本性陷阱

当前 Infinigen 固定版本中的资产源码可能包含历史分支或局部缺陷。复用前按以下顺序核对：

1. `create_asset` 是否真的消费 `dimensions`、`params` 或采样结果；不要因为签名存在就认为约束生效。
2. `sample_parameters`、Geometry Nodes 输入和实际几何分支是否名称一致；忽略未使用字段。
3. placeholder、`NoApply`、空 `finalize_assets`、被注释材质调用和不可达分支不能作为目标能力。
4. 返回对象是否是完成加厚、合并和赋材质后的对象，而不是处理中间对象。
5. 私有 nodegroup/helper 是否只在原文件内部稳定；不能通过复制名称假设它是公共 API。
6. 房间级、scatter、simulation、joint、lighting 和导入期场景行为不能进入静态单体 `asset.py`。

若完整 Factory 能安全实例化，优先直接使用。若发现上述问题，只提取已经用预览验证的可见机制，
并改用公开 Blender/Infinigen API 实现；不要为了保留“原生复用”名义复制缺陷代码。
