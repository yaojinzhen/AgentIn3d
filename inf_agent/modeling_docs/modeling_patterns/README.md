# 建模模式目录

本目录保存可复用的几何与装配决策卡，回答“这种形态应该怎样构造”，不保存完整资产教程。
运行时通过 `python -m inf_agent.cli query pattern --query "..."` 查询带 frontmatter 的卡片；本文件只说明维护边界，不参与查询。

## 职责边界

- 原生 Factory 与具体资产事实：`asset_examples/objects`。
- 材质语义与选择：`asset_examples/materials`。
- 几何构造方法与适用边界：本目录。
- API 签名及少量可复用代码骨架：`api_reference`。
- 失败修复：`troubleshooting`。

不再建立独立的代码示例层。正文统一使用中文；稳定文件名、`id`、API 名和代码保持英文，`aliases` 同时保留中英文查询词。
