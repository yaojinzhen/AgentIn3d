# 三维资产建模知识库

`modeling_docs` 是 Infinigen 单体资产 Agent 的专用建模知识库。它只保存会直接帮助 Agent
选择参考、决定建模方法、编写 API、设计材质或诊断失败的长期知识；使用、架构和维护说明统一保存在 [`../docs/`](../docs/README.md)。

正常生成任务优先通过统一 CLI 查询所需知识：

从仓库根目录使用根 `.venv`；平台命令写法见[使用指南](../docs/USER_GUIDE.md#环境与入口)。

```bash
./.venv/bin/python -m inf_agent.cli query <object|pattern|api|material|troubleshoot> --query "<内容>"
```

查询默认返回至多三项，可用 `--limit` 指定其他正整数；这不是阅读量或建模执行限制。
建议先读取与当前操作最相关的叶子文档，必要时继续读取普通文档与源码。
`indexes/*.json` 是机器索引，日常检索无需整份加载；维护和调试时可以直接检查。

查询后将 `document_path` / `documents[]` 原样传给 `read --document`，将
`source_symbols[]` 原样传给 `read --symbol`。章节标题与文件路径分开返回；目录、模块、
源码位置和外部 Blender API 位于带类型的 `source_references[]`，不属于符号 reader 输入。

## 目录职责

| 目录 | 回答的问题 |
| --- | --- |
| `asset_examples/objects/` | 是否存在高度匹配的原生 Factory，哪些机制和依赖值得复用 |
| `asset_examples/materials/` | 材质应呈现怎样的颜色、响应、变化层次和可见尺度 |
| `modeling_patterns/` | 某种主体形态适合用哪种几何构造方式 |
| `api_reference/` | 精确函数、材质接口、节点、socket 和代码操作怎样调用 |
| `troubleshooting/` | 已经观察到的失败属于哪个域，怎样做最小修复 |
| `indexes/` | 查询器消费的可重建机器索引及维护说明 |

## 查找链路

```text
query object
  -> 精确对象命中：读取一份对象卡及其明确指向的原生源码或 Pattern
  -> 没有命中：按主体形态 query pattern
  -> 编写具体代码操作时 query api
  -> 决定材质外观时 query material
  -> 出现真实失败后 query troubleshoot
```

对象未命中不表示不支持。不得回退到字符相似对象或强制映射到单一资产分类，也不得因为缺少
对象卡而拒绝静态单体资产。存在高度匹配的原生 Factory 时优先直接复用或窄适配；否则组合
主体形态、结构特征、材质语义和场景属性自主建模。Primitive、轮廓旋转、曲线扫掠、自定义
mesh、Geometry Nodes 和混合建模都允许，选择依据是对象结构而不是复杂度标签。

## 内容准入

- 具体对象和原生复用事实进入 `asset_examples/objects/`；
- 材质视觉语义进入 `asset_examples/materials/`；
- 可跨对象复用的几何决策进入 `modeling_patterns/`；
- 接口签名、调用事实和兼容性进入 `api_reference/`；
- 有真实证据、可复现的失败诊断进入 `troubleshooting/`。

单次资产的参数调整、临时补丁、视觉结论、开发计划和验收统计不属于本知识库。正文统一使用
中文；稳定 ID、文件名、Python/API 符号和必要中英文 aliases 保持英文。修改 API 文档后必须
保证既有函数、材质和节点接口不丢失，并通过生成器重建、检查索引。
