# GLB 导出与材质转换

本页维护当前 GLB 材质转换行为、Infinigen 复用范围与设置。文件字段见[输出格式](OUTPUT_FORMAT.md)。

## 导出行为

从仓库根目录使用根 `.venv`，平台命令写法见[使用指南](USER_GUIDE.md#环境与入口)。

```bash
./.venv/bin/python -m inf_agent.cli export --workspace <workspace>
./.venv/bin/python -m inf_agent.cli export --workspace <workspace> --texture-resolution 2048 --bake-samples 4
```

默认贴图为 2048×2048，Cycles CPU 采样 4；分辨率允许 64–4096，采样允许 1–128。
小型资产可降低分辨率提高速度；细斑点、织纹与近景需要足够的纹理密度。
常量 PBR 材质直传，不为了“有贴图”而生成无意义图片；与输入连接的颜色/纹理/程序化子网自动烘焙。

转换使用独立场景、求值后的 mesh 和材质副本；原始 asset.py、BLEND 程序化节点、相机与预览不被烘焙过程修改。
导出后清理临时数据并恢复原场景，即使转换失败也执行恢复。
每次 export 仍创建新运行，计入每工作区默认 20 次额度；validate 不重新烘焙。

material_export.json 记录每个材质的 direct_pbr / baked、烘焙通道、设置和静态验证。
textures/*.png 保留便于检查，GLB 内嵌所有图像，传输 GLB 无需同时携带该目录。

## Infinigen 接口与适配

| Infinigen 接口 | 用途及适用性 |
| --- | --- |
| tools/export.py export_curr_scene、export_scene | 整场景导出；包含对象/层级处理、UV、烘焙和格式写出 |
| export_single_obj | 单对象入口，复用同一烘焙链路 |
| export_sim_ready | 仿真视觉/碰撞资产导出 |
| run_blender_export | OBJ、FBX、USD、STL、PLY 等格式写出；当前没有 GLB 分支 |
| bake_object、bake_scene | 完整材质烘焙流程；会改写材质并使用部分材质名称启发式 |
| bakeVertexColors | 顶点色烘焙；密集斑点/织纹受网格密度影响，不作为本次默认路径 |
| core/sim/exporters/usd_exporter.py | USD 仿真导出；其材质烘焙仍调用 bake_object |
| core/util/exporting.py | mesh/实例/语义等数据导出，不是程序材质转 GLB 的替代实现 |

上述高层入口没有直接可用的 GLB 选项，且有场景改写、旧 cycles.tile_x/tile_y 等问题。
GLB 转换复用 tools/export.py 的 deep_copy_material、uv_unwrap、bake_pass、apply_baked_tex，
最后仍由 Blender 自带 glTF 导出器写出 GLB。UV 和实际烘焙仍由 Infinigen / Blender 算子执行。

适配所用的可选参数：

- uv_unwrap 接受 UV 岛边距，避免贴图扩边互相串色。
- bake_pass 接受烘焙类型覆盖和色彩空间；颜色/标量输入通过 EMIT 独立求值，避免灯光、金属、涂层影响底色。
- apply_baked_tex 接受额外通道映射；材质常量由适配层逐材质保存/恢复，不依赖只返回最后一材质的参数收集函数。

## 支持范围与检查

支持直接 Principled BSDF，以及输出最终为 Principled 的嵌套 Shader Group；节点组内部保留原图求值，
不复制实现 Noise、Voronoi、Wave、ColorRamp 等节点算法。常量通过组接口正确解析，颜色与数据贴图区分 sRGB / Non-Color。
可转换底色、粗糙度、金属、法线和适配层声明的其他 PBR 输入；常量 coat、sheen、IOR、transmission 等保留。
已连接的图像纹理也按目标分辨率重采样；当前不承诺任意 shader 混合、所有扩展或逐像素完全相同。

无法映射的表面（如 Mix Shader）和未实现到几何中的 displacement 会返回明确错误，避免静默输出白模。
如需复杂表面，应先采用可导出的 Principled 结构或将几何位移实际求值到 mesh。

文件检查验证内嵌 PNG/JPEG 可以完整解码、texture/material 索引有效、对应 UV 集存在，再由独立 Blender 重开。
这些检查不证明通用视觉相似度；交付前仍要实际查看导入后的 GLB，尤其是材质边界、织纹和透明材料。

功能与兼容范围见 [1.1 发布说明](RELEASE_NOTES.md)，运行和验证命令见 [使用指南](USER_GUIDE.md)。
