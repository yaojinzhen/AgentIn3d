---
id: display-devices-native
domain: object
intent: 电视和显示器的原生硬表面路线
aliases: ["television", "tv", "monitor", "display", "电视", "显示器", "电脑显示器"]
use_when: "创建由屏体、屏幕凹槽、后壳、支腿或桌面支架组成的显示设备。"
avoid_when: "目标是手机、笔记本电脑、投影仪或只需一个发光平面的场景道具。"
source_symbols: ["infinigen/assets/objects/appliances/tv.py:TVFactory", "infinigen/assets/objects/appliances/tv.py:MonitorFactory"]
related_patterns: ["hard-surface-negative-space", "rigid-assembly"]
summary: "复用 TVFactory 或 MonitorFactory 的屏体、凹槽和支撑关系；屏幕不是贴在方盒上的纯黑平面。"
---

# 显示设备原生参考

电视优先使用 `TVFactory`，显示器使用 `MonitorFactory`。先建立屏体厚度、边框、屏幕凹槽和
后壳，再从局部坐标推导双支腿或单支架。屏幕材质需要受控高光或发光，并保留边框和背板；
支架底座必须接触地面或桌面，不能悬空。
