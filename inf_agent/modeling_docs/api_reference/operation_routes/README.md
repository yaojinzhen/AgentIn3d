# API 操作路由

本目录保存 query api 使用的机器路由源，把尚无精确接口名的代码操作直接映射到一至三份 API 叶子文档。正常资产生成只消费查询结果，不再读取本目录中的中间卡片。

## 路由顺序

1. 查询词精确命中源码符号时，直接返回该符号及其主叶子文档。
2. 查询词精确命中文档化接口（包括 raw bl_idname）时，直接返回所属叶子文档。
3. 没有精确接口时，才匹配本目录的自然语言操作路由。
4. 操作路由未命中时，才返回有文档关联的低置信度源码符号或下一步建议。

## 元数据契约

每个路由文件必须包含 id、domain: api、intent、aliases、use_when、avoid_when、source_symbols、related_patterns、documents 和 summary。

`documents` 是相对 `modeling_docs` 的路径列表，必须包含一至三份 Function API、Material API
或 Node API 叶子文档；禁止指向 README、其他操作路由、Pattern、对象卡或索引 JSON。

本目录不记录函数签名、socket、参数或建模策略，也不参与 API 符号与叶子文档的关联。索引生成器只扫描三类 API 叶子文档。
