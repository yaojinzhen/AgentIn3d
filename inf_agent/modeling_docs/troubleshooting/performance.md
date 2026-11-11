---
id: troubleshoot-performance
domain: troubleshoot
intent: 诊断资产复杂度造成的几何量、节点数、渲染时间、内存或预览超时
aliases: ["performance", "too many vertices", "render timeout", "memory", "性能问题", "顶点过多"]
use_when: "日志和指标证明重复瓶颈来自资产复杂度，而不是环境启动或一次性外部超时。"
avoid_when: "外部超时或框架失败尚未稳定复现。"
source_symbols: []
related_patterns: ["geometry-nodes-distribution"]
summary: "在保留身份、轮廓和必要特征的前提下，减少不可见微细节、实例数量和过早 realize。"
---

# 性能失败

先证明成本来自 evaluated geometry 或材质复杂度。然后移除或延迟低于预览分辨率的细节，
限制实例数量，避免不必要的 realize、subdivision 和昂贵 shader 层。

不得用占位体替换可识别形态。性能修复必须保留主轮廓、附件连接、材质基础响应和用户明确
要求的特征；环境启动慢不属于本卡处理范围。
