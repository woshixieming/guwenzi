# 本地字体与授权

页面通过 `index.html` 的 `@font-face` 注册字体，再由每种书体的 CSS 绑定到字形卡片。
仅注册或预加载字体不会改变卡片实际显示的书体。

## 网页书法字体

以下字体已保存到本地，保留原 WOFF2 文件及其字符分片；CSS 仅保留本地 WOFF2 源。
页面按需加载字形，不再访问字体 CDN。

| 字体 | 固定包版本 | 本地目录 |
| --- | --- | --- |
| 霞鹜文楷 Screen | cn-fontsource-lxgw-wen-kai-screen 1.0.6 | `web/kai/` |
| 思源宋体 SC VF | cn-fontsource-source-han-serif-sc-vf-regular 1.0.1 | `web/song/` |
| 马善政毛笔楷书 | @fontsource/ma-shan-zheng 5.3.1 | `web/mao/` |
| 志莽行书 | @fontsource/zhi-mang-xing 5.3.0 | `web/xing/` |
| 柳建毛草 | @fontsource/liu-jian-mao-cao 5.3.0 | `web/cao/` |

这些字体采用 SIL OFL 1.1，原授权文件保存在各目录。
霞鹜文楷和思源宋体的 npm 包未附许可证，因此分别补存了原作者仓库的 OFL 文件。
下载包的完整性校验及本地文件哈希记录在 `assets/offline-manifest.json`；
用 `python3 scripts/sync_offline_assets.py --check` 可离线校验。

## 甲骨文

- 页面文件：`jiaguwen.woff2`，CSS 字体名 `JiaGuWen`。
- 文件内部字体名：`Oracular`，版本 `1.001`（2024-10-04）。
- 内部版权信息：Copyright (c) Peichao, Qin, 2023. All rights reserved.
- 官方资源：[镜原甲骨字库下载](https://oracular.azurewebsites.net/glyphs/download)。
- 字形与编码说明：[官方字库说明](https://oracular.azurewebsites.net/glyphs/docs)。
- 项目已有记录记载其采用 SIL Open Font License 1.1，但本地未附完整许可副本和下载版本凭据；
  当前官网可访问不等于已核实本地文件的许可，进一步再分发或修改前需补齐核验。

官网字库包含大量异体与私用区字形，不代表所有现代汉字都有直接对应的甲骨字形。
当前页面用现代汉字码位查找本地字体，覆盖记录在 `data/coverage_orac.txt`。
规范字在 `data.js` 中的缺字位掩码由 `scripts/build_data.py` 生成；
更换字体后须核对实际字符映射与覆盖表，不能只替换字体文件。

## 隶书

- 文件：`moe-lishu.ttf`，CSS 字体名 `MoeLi`，内部名称 `TW-MOE-Li`。
- 版本：3.00（June, 2019），按需加载约 5.0 MiB 的完整原始字体。
- 来源：[教育部隶书官方页面](https://language.moe.gov.tw/material/info?m=9fe3fb11-c3d5-41f2-b029-6d18a2c2fd0d)。
- 署名：中華民國教育部；授权为 CC BY-ND 3.0 TW，详见 `moe-lishu-LICENSE.md`。
- 字体未修改、子集化或转换，文件内容与官方下载包一致。

根据字体的 Unicode 映射及非空轮廓生成 `lishu-coverage.js`：

```bash
python3 scripts/build_lishu_coverage.py
```

在项目 8,105 个规范字中，3,074 个可直接显示；1,360 个有明确的单字繁体对应，
页面显示繁体字形并标注「繁体某字字形」；其余 3,671 个显示未收录。
不从多字繁体写法中擅自选择，也不使用系统字体冒充隶书。
隶书覆盖由独立表判断，不改动原有 `data.js` 的八体缺字位掩码。

## 其他书体

- `shuowen.woff2`：说文小篆，CSS 字体名 `ShuoWenZhuan`。
- `ysbzt.woff2`：峄山碑篆体，CSS 字体名 `YiShanBeiZhuan`。

这两套本地文件尚未完整保留作者授权、下载版本及转换/合并过程的凭据，
不能仅凭其他网站的“免费商用”标签，或候选上游的许可，认定当前文件可转换和再分发。
资源使用情况与待核实事项见 [项目来源清单](../README.md) 和 [数据许可说明](../assets/licenses/README.md)。

篆书卡片按 `峄山碑 → 说文小篆` 的顺序选择同一汉字的字形；
两者均缺字时才显示“未收录”，并保留现代字形作为灰色参照。
卡片来源和字体加载状态跟随实际选中的字体，列表的缺字数也按补充后的覆盖计算。
说文小篆补充字形不表示该字见于《峄山刻石》，页面不会将补充字形标成峄山碑来源。

`seal-coverage.js` 由 `python3 scripts/build_seal_coverage.py` 生成，
输入为 `data/coverage_zhuan.txt` 与 `data/coverage_seal.txt`。
更换字体或更新覆盖表时应重新运行此脚本。
目前两套字体合计覆盖 6,154 个规范字，比峄山碑单独覆盖的 3,751 个多 2,403 个。

可进一步评估的资源：

- [崇羲篆体](https://xiaoxue.iis.sinica.edu.tw/chongxi/)：官网介绍覆盖 11,596 字，
  包含《说文》字形与部分后起字转写；
  [授权](https://xiaoxue.iis.sinica.edu.tw/chongxi/copyright.htm)为 CC BY-ND 3.0 TW 或后续版本，要求署名且禁止改作。
  2026-10-20 检查时，官方 ZIP 下载在当前网络返回访问限制页面，尚未接入。
- [霞鹜篆书](https://github.com/lxgw/LxgwSeal)：OFL 1.1，当前覆盖规模较小，尚未作为补充字体接入。

`data/` 下的原始字体与 `fonts/` 下的页面字体不是同一文件，不能仅因名称相近视为重复文件。
