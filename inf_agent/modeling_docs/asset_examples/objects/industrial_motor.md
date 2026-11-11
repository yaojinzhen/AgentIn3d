---
id: industrial-motor
domain: object
intent: 工业电动机的形态路线
aliases: ["industrial motor", "electric motor", "电机", "工业电动机"]
use_when: "创建具有轴向机壳、端盖、转轴、散热片、接线盒和安装脚的静态电机。"
avoid_when: "用户需要工程精确的内部结构、动画或认证尺寸。"
source_symbols: []
related_patterns: ["profile-revolve-shell", "geometry-nodes-distribution", "rigid-assembly"]
summary: "机壳使用旋转构造，散热片使用有界分布，安装脚和接线盒使用刚性装配。"
---

# 工业电机形态参考

将电机视为混合构造。轴向机壳和端盖采用旋转或放样，散热片采用受控分布，转轴、安装脚和
接线盒使用规则模块。附件位置应从机壳坐标框架推导，不能堆叠互不关联的 primitive。
