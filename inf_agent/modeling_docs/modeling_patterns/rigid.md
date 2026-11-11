---
id: rigid-assembly
domain: pattern
intent: 使用共享局部坐标系和明确接触关系装配规则刚性部件
aliases: ["rigid assembly", "table frame", "刚体装配", "框架支撑", "模块装配"]
use_when: "对象由面板、梁、支腿、支架或紧固件等规则刚性零件组成。"
avoid_when: "主体识别依赖连续有机体、柔性体或复杂曲面。"
source_symbols: []
related_patterns: ["hard-surface-negative-space", "geometry-nodes-distribution"]
summary: "先定义承载结构和共享坐标系，再从表面与端点推导从属部件，避免悬空和盲目堆 primitive。"
---

# 刚体装配

规则面板、桌腿、紧固件和支架可以使用 primitive；连续外壳或有机主体不能由大量重叠 primitive
勉强近似。先建立共享坐标系和承载面，再从边界、厚度、端点和 inset 推导从属部件。重复件使用
同一源对象或函数。parenting 只表达所有权，不能代替真实接触；需要时增加套环、铰链、支架或紧固件。

混合资产应按组件形态分别选方法：连续外壳使用 mesh/loft，规则支脚使用 primitive，线缆使用 curve
sweep；所有附件仍从同一承载体坐标系推导，不能各自使用看似接近的独立比例。
使用 `AssemblyBuilder.material_region` 时，第二参数是注册时使用的 part-id 字符串列表，
如 `["body"]`，不是 `register()` 返回的 registration handle；这是运行时硬约束。

## 方法专属验证

正面和侧面检查端点接触，顶面检查布局，透视图检查整体受力路径。允许少量消除视觉缝隙的重叠，
但深度穿插不能改变轮廓。若大量 primitive 正在近似一个连续模塑主体，应更换主构造方法。
