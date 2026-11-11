---
id: hand-tools-mechanisms-native
domain: object
intent: 钳子、胡椒研磨器和小型五金机构的静态原生参考
aliases: ["pliers", "plier", "pepper grinder", "hardware mechanism", "钳子", "胡椒研磨器", "研磨器", "小型五金"]
use_when: "创建由工作头、手柄、中心轴、旋转主体、安装座或连接杆组成的静态工具和机构。"
avoid_when: "需求需要关节动画、物理约束、工程级内部结构或认证尺寸。"
source_symbols: ["infinigen/assets/sim_objects/plier.py:PlierFactory", "infinigen/assets/sim_objects/pepper_grinder.py:PepperGrinderFactory", "infinigen/assets/objects/bathroom/hardware.py:HardwareFactory"]
related_patterns: ["rigid-assembly", "profile-revolve-shell"]
summary: "只借鉴静态几何关系，保留工作头、手柄、轴和紧固件身份，不复制 simulation 或 joint 元数据。"
---

# 手工具与小型机构参考

钳子由成对钳臂、手柄包覆、钳头和中心轴组成；胡椒研磨器由回转主体、底脚、颈部、顶盖或摇柄
组成；卫浴五金由安装座、连接杆、挂钩或圆环组成。`sim_objects` 中的 Factory 仅作为静态结构
参考，不能把 joint、damping、stiffness 或仿真注册复制进 `asset.py`。
