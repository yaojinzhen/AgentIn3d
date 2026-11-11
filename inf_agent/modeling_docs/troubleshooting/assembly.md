---
id: troubleshoot-assembly
domain: troubleshoot
intent: 诊断悬空、脱离、严重穿插或连接方式不可信的附属部件
aliases: ["assembly failure", "floating part", "detached", "penetration", "悬空", "未贴合", "装配错误"]
use_when: "依附部件与承载主体存在间隙、严重穿插、错误锚点，或缺少合理连接件。"
avoid_when: "实际失败来自根主体的支撑关系，或与装配无关的几何、材质问题。"
source_symbols: []
related_patterns: ["rigid-assembly", "curve-sweep"]
summary: "依据承载表面、端点或共享局部坐标系重新计算附属部件，并补充真实物体需要的连接结构。"
---

# 装配失败

至少在两个视图中检查依附部件。位置应由承载表面、端点或共享局部坐标系计算，不能继续
叠加任意比例偏移。仅靠父子关系或 AABB 重叠不能证明连接成立；真实物体需要时，应增加
果梗、插槽、支架、套环、铰链或紧固件。

允许为避免视觉缝隙保留少量有意重叠，但必须修复明显间隙、改变轮廓的深度穿插和没有
结构解释的接触。只修改失败的锚点或连接结构，不因一个附件问题重建整个资产。
