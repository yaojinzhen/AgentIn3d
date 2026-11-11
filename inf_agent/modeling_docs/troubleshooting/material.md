---
id: troubleshoot-material
domain: troubleshoot
intent: 诊断材质未分配、颜色错误、纯色或映射尺度不合理
aliases: ["material failure", "wrong color", "pure color", "near white", "unassigned material", "材质错误", "颜色错误"]
use_when: "几何已经可识别，但渲染颜色、粗糙度、映射或材质语义错误。"
avoid_when: "主轮廓或必要几何仍然错误。"
source_symbols: []
related_patterns: []
summary: "先验证材质分配和基础响应，再检查映射尺度与受控变化；节点存在不代表通过。"
---

# 材质失败

先确认目标材质已经分配给 evaluated mesh。在中性预览光照下修正基础色相、明度和粗糙度，
之后才添加噪声、凹凸、磨损或复杂节点。检查坐标来源，以及纹理变化在最终物体尺度上是否
可见且合理。

绿色叶片渲染为近白、果皮呈纯色塑料，或请求材质没有实际分配时，即使节点数量很多也应
失败。只修复材质域，不用材质复杂度掩盖几何问题。
