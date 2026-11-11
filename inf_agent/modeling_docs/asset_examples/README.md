# 资产与材质参考路由

本目录保存 Agent 建模时可按需检索的精选路由文档，不是 Infinigen 全量资产目录，也不是
逐次运行的经验日志。正常工作应通过统一 CLI 查询，不要先遍历本目录：

```bash
python -m inf_agent.cli query object --query "<对象名称>"
python -m inf_agent.cli query material --query "<材质名称或外观要求>"
```

## 目录职责

- `objects/`：具体对象或共享同一实现路线的紧密对象组的小型路由文档。记录可靠的原生
  Factory、值得保留的机制、私有依赖风险和下一步 Pattern。它是精选集合，不要求覆盖全部
  Infinigen 对象，也不得重新扩展成历史八大类别。
- `materials/`：材质语义与外观设计的小型路由文档。公共调用签名仍由
  `../api_reference/material_api/` 负责。

每份可查询文档都必须包含 `domain` frontmatter。`query object` 只检索 `objects/*.md`，
`query material` 只检索 `materials/*.md`；二者不会相互 fallback 或跨域猜测。

## 对象查询链路

对象查询命中高置信度路由时，只读取返回的文档以及其中明确指向的 Pattern、API 或原生源码
符号。当前代表性路由包括苹果、阔叶、蘑菇、岩石、陶瓷盘、餐桌、工业电机和硬壳行李箱。

没有命中并不表示对象不受支持。此时应根据主体形态改查 `query pattern`，再结合结构特征、
材质语义和场景属性自主建模。不得用字符相似的对象勉强 fallback，也不得强制映射到单一资产
分类。

## 材质查询链路

先用 `query material` 确定材质语义、基础响应、变化层次和可见尺度；只有编写具体节点或调用
材质函数时，才继续查询 Material API。不要同时读取多个相近材质文档和大段 API。

## 原生复用边界

存在高度匹配的原生 Factory 时，优先直接使用它，并通过参数、确定性采样或必要的窄适配满足
请求。只有形态不兼容或原生依赖无法安全隔离时才重新建模。读取原生实现时，只展开选定符号
及其直接依赖；不要复制导入期场景操作、scatter、simulation、camera、render 或 output 逻辑。

## 文档准入规则

本目录不自动记录每次建模经验。只有经过验证、能够稳定改变后续路由决策的知识才可加入：

- 具体对象存在准确或高价值的原生实现路线时，加入 `objects/`；
- 材质语义、入口和尺度原则稳定且可复用时，加入 `materials/`；
- 通用几何方法进入 `modeling_patterns/`；
- API 签名进入 `api_reference/`；
- 可复现失败及诊断进入 `troubleshooting/`。

单次资产的参数调整、临时补丁和视觉结论应保留在对应 workspace 或 evaluation 中，不能直接
写成长期路由知识。正文统一使用中文；稳定 `id`、文件名、Python/API 符号保持英文，
`aliases` 同时保留必要的中英文查询词。
