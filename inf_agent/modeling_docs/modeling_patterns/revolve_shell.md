---
id: profile-revolve-shell
domain: pattern
intent: 从有意义的内外侧轮廓构造回转壳体、容器、法兰、轮体和轴向外壳
aliases: ["profile revolve", "revolve", "lathe", "rotational shell", "旋转轮廓", "回转体", "回转壳体"]
use_when: "主体的大部分截面围绕同一轴连续旋转。"
avoid_when: "圆周方向明显不对称，或主体主要沿自由路径延伸。"
source_symbols: ["infinigen.assets.objects.tableware.cup", "infinigen.assets.objects.tableware.bottle"]
related_patterns: ["hard-surface-negative-space", "custom-mesh-loft"]
summary: "采样能表达轮廓转折的内外 profile，保持正壁厚并按实际闭合关系连接和封口。"
---

# 轮廓旋转与壳体

用有序 `(radius, height)` 样本描述侧轮廓，在卷边、肩部、足部、法兰和颈部增加采样，直线段保持
稀疏。杯、盘、瓶口或空心外壳必须具有独立内外轮廓，并在口沿和必要底部连接；深色圆盘不能代替
空腔。墙厚在紧曲率处仍须为正，只有真实闭合面才封口。

## 方法专属验证

检查法线反转、极点夹紧、环距突变、开缝、零厚度口沿和高光分面。正面与侧面验证 profile，顶面
验证圆周连续性，透视图验证空腔和底足。分段数只能消除可见分面，不能修复错误轮廓。

