---
id: troubleshoot-geometry
domain: troubleshoot
intent: 诊断空 mesh、异常 bounds、严重拓扑或错误轮廓
aliases: ["proportions", "dimensions", "outside the 15% tolerance", "尺寸偏差", "asset_failure geometry", "empty mesh", "invalid bounds", "non manifold", "silhouette", "网格错误", "轮廓错误"]
use_when: "preview 已执行，但客观 mesh health 或视觉身份、轮廓失败。"
avoid_when: "失败仅来自材质外观、悬空附件或环境状态。"
source_symbols: []
related_patterns: ["modeling-strategy", "custom-mesh-loft"]
summary: "区分硬性 mesh 无效与视觉形态错误，先修复主轮廓或拓扑，再考虑细分和细节。"
---

# 几何失败

对于无 mesh、零 bounds、NaN/Inf 或严重 evaluated topology 错误，先定位失败对象和
modifier。对于 mesh 有效但对象不可识别的情况，返回主形态 Pattern，修复 profile、截面、
宏观比例或受控形变。

增加顶点不能修复错误比例。单个非阻塞细长面也不应触发整体重建；只处理影响身份、轮廓、
必要特征或稳定执行的最高优先级问题。


## 显式尺寸偏差

收到 `explicit width/depth/height is outside the 15% tolerance` 时，读取
`objective_validation.json → layers.objective_asset_health.explicit_dimensions`。
对照 expected_m、observed_m 和 relative_error 核对模型尺度、轴向和单位；
运行成功但尺寸失败仍是客观失败。修正 asset.py 后重新 preview/export。
文件和结果字段职责见[产物格式](../../docs/OUTPUT_FORMAT.md)。
