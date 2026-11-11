---
id: troubleshoot-native-reuse
domain: troubleshoot
intent: 诊断私有原生 helper、复制 Factory 或依赖不完整造成的复用失败
aliases: ["private api", "native reuse", "copied factory", "私有 API", "原生复用失败"]
use_when: "原生薄适配因私有 helper、注册、配置或场景依赖缺失而失败。"
avoid_when: "精确原生 Factory 可以安全实例化，或错误与复用无关。"
source_symbols: []
related_patterns: ["modeling-strategy"]
summary: "检查直接依赖，优先包装公开 Factory；必要时只提取可见机制，不复制场景或散布副作用。"
---

# 原生复用失败

检查目标符号能否稳定导入，以及是否依赖 registry、配置、场景、scatter 或全局状态。优先
包装完整且可安全实例化的原生 Factory。若完整 Factory 不适用，只使用已验证的公开 API
复现必要的局部几何或材质机制，并在 `design.md` 中简要说明原因。

不得把大型原生模块、私有场景初始化、散布逻辑、相机、渲染或输出行为复制进 `asset.py`。

成功导入不等于适合复用。若参数无效、材质未应用、返回对象不完整或命中 placeholder，继续查询
`native_source_quirks.md`，先确认当前固定版本的真实执行路径。
