---
id: troubleshoot-randomness
domain: troubleshoot
intent: 诊断生成资产不可复现，或随机变化破坏必要特征
aliases: ["random seed", "nondeterministic", "variation failure", "随机性", "不可复现"]
use_when: "相同候选重复执行结果不同，或随机性移除必要特征、破坏比例与连接。"
avoid_when: "差异来自请求、代码、运行参数或环境已经改变。"
source_symbols: ["infinigen.core.util.math:FixedSeed"]
related_patterns: []
summary: "为所有变化设置稳定 seed，将随机幅度限制在结构尺度以下，并让用户明确约束处于随机采样之外。"
---

# 随机性失败

使用 `FixedSeed` 和稳定派生 seed。所有采样范围必须保持对象身份、比例和必要特征。随机性
可以改变一个有效苹果、叶片、桌子或岩石的细节，但不能改变对象类型、删除把手、分离果梗，
或覆盖用户明确的尺寸和颜色。

先比较请求、设计、代码和运行参数的候选 hash；只有输入完全相同时，结果差异才属于不可
复现问题。

从原生源码借鉴采样时，必须重新确认上界和权重语义：`randint(a, b)` 与 `RI(a, b)` 的上界
通常不包含 `b`，概率数组必须归一化，固定 seed 需要同时覆盖参数和材质采样。不要把整数上界
误当作可取值，也不要用一次偶然采样结果证明必要部件始终存在。
