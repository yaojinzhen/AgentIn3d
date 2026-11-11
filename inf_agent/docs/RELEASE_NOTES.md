# Agent 1.1 发布说明

工作区和运行输入使用 `schema_version="2"`。

## 功能

- 文字或单主体图片驱动的静态单体建模，支持原生 Factory、自定义几何、节点与材质。
- 对象、API、材质与故障知识检索，以及相关源码读取。
- 独立运行与输入快照，支持声明的本地模块、资源与参考图。
- 多视图预览、几何与装配诊断、BLEND/GLB 导出及独立重开验证。
- GLB 内嵌贴图，保留可编辑的程序化 BLEND。
- 默认每工作区最多 20 次 preview/export，可显式调整预算。
- `in3d-generate-asset` 用于生成与修改，`in3d-run-asset` 用于执行与诊断，按目标 Agent 的规则注册。

## 兼容范围

- 环境为 Python 3.11、bpy 4.2.0，安装方式见[根 README](../../README.md)。
- 旧协议工作区需按当前输入格式重新准备。
- GLB 支持直接 Principled 及输出为 Principled 的嵌套节点组。无法映射的表面和未实现到几何中的 displacement 会报错。
- 几何检查依据已声明约束与实际测量范围。视觉是否符合需求由实际看图确认，程序的 `visual_status` 保持 `NOT_CHECKED`。
- 资产 Python 使用当前用户权限，执行边界见[使用指南](USER_GUIDE.md#执行边界)。

详细接口见[使用指南](USER_GUIDE.md)、[输出格式](OUTPUT_FORMAT.md)和 [GLB 导出](GLB_EXPORT.md)。
