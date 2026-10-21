# 汉字书体溯源

一个面向汉字学习、书体对照与古籍查阅的静态网站，将汉字查询、繁简异体关系、字义和笔顺展示集中在同一页面。

## 可以做什么

- 按汉字、带调或不带调拼音查询，支持现代部首、康熙部首和笔画检字。
- 对照楷体、宋体、毛笔楷、隶书、行书、草书、篆书、说文小篆和甲骨文字形。
- 查阅繁体、异体、部件拆分、字义、古籍书证和词语读音。
- 识别家谱等文本中的繁体、异体和旧字形，辅助定位现代通行字。
- 不知道读音也能按原字部首、笔画找异体字，查看对应规范字候选及来源；支持部件筛选与分页。
- 支持截图选字、裁剪和大模型识字候选确认；OCR 需另行配置服务，未配置时仍可使用部首查找。
- 查看笔顺动画；运行资源保存在本地，正常查询无需外部 CDN。

字形展示受字体收字范围和编码映射限制；字体中的现代汉字对应字形不等于历史出土字形的直接证据。
部件拆分用于检索，不应直接作为字源结论。多音、异体关系及古籍引文仍需结合上下文与权威资料核对。

## 数据来源与署名

以下列出项目使用的数据及参考来源。上游项目的许可不替代对其所收录原始材料的权利核实；
未能确认来源或再分发许可的部分在后文单列。

| 资源 | 来源与权利信息 | 本项目中的处理 |
| --- | --- | --- |
| 规范字及繁异体对照 | 《通用规范汉字表》（2013）及其《规范字与繁体字、异体字对照表》；现有原始文件未完整记录下载出处 | 整理字级、检索索引与对照关系；原始文件来源仍待补齐 |
| 生僻字读音、部首、变体关系 | [Unicode Unihan](https://www.unicode.org/reports/tr38/)，Unicode, Inc.；本地数据头标明 Unicode 18.0.0，[Unicode 许可](https://www.unicode.org/license.txt) | 提取读音、部首与变体字段，生成扩展查询数据 |
| 繁简转换 | [OpenCC](https://github.com/BYVoid/OpenCC)，[Apache-2.0](assets/licenses/OpenCC-LICENSE.txt) | 提取单字繁简关系，作为查询补充；不是完整 OpenCC 转换引擎 |
| 部件拆字、繁简索引 | [漢語拆字字典](https://github.com/kfcd/chaizi)，© 2015 開放詞典，[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) | 从简繁拆字表和索引整理部件及反查关系，生成前端索引 |
| 词语拼音、繁简词形 | [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cc-cedict)，CC-CEDICT 贡献者 / MDBG；源于 Paul Andrew Denisowski 发起的 CEDICT，[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | 筛选词条、转换拼音声调、合并读音并分片；对应 CC-CEDICT 改编数据按同一许可提供 |
| 字义、结构、频率、部分繁异体字段 | [《汉语拼音辞典》](https://github.com/mapull/chinese-dictionary)，© 2021 码谱，上游仓库标注 [MIT](assets/licenses/ChineseDictionary-LICENSE.txt)；本地脚本标注此来源，但未记录下载版本 | 从 char_base.json、char_detail.json 提取字段、截取释义和书证；原始辞书材料权利及版本对应关系仍待核实 |
| 主字库基础拼音、部首等 | data/gsc_pinyin.csv；旧页面称其来源为“开源新华字典数据”，当前仓库未保存可核实的具体上游和许可 | 用于生成主字库；来源与再分发许可待核实 |

Unicode、OpenCC、拆字数据及辞典上游的许可文本副本见 [资源许可目录](assets/licenses/)。
上述名称用于说明资料来源，不表示本项目获得相关机构或作者的认可、合作或背书。

## 字体与笔顺资源

| 资源 | 作者或上游 | 许可与说明 |
| --- | --- | --- |
| 霞鹜文楷 Screen | [LXGW](https://github.com/lxgw/LxgwWenKai-Screen) | [SIL OFL 1.1](fonts/web/kai/OFL.txt) |
| 思源宋体 | [Adobe / Source Han Serif](https://github.com/adobe-fonts/source-han-serif) | [SIL OFL 1.1](fonts/web/song/OFL.txt) |
| 马善政毛笔楷书 | [Google Fonts / Ma Shan Zheng](https://fonts.google.com/specimen/Ma+Shan+Zheng) | [SIL OFL 1.1](fonts/web/mao/LICENSE) |
| 志莽行书 | [Google Fonts / Zhi Mang Xing](https://fonts.google.com/specimen/Zhi+Mang+Xing) | [SIL OFL 1.1](fonts/web/xing/LICENSE) |
| 柳建毛草 | [Google Fonts / Liu Jian Mao Cao](https://fonts.google.com/specimen/Liu+Jian+Mao+Cao) | [SIL OFL 1.1](fonts/web/cao/LICENSE) |
| 教育部隶书 3.00 | [中華民國教育部](https://language.moe.gov.tw/material/info?m=9fe3fb11-c3d5-41f2-b029-6d18a2c2fd0d) | [CC BY-ND 3.0 TW](https://creativecommons.org/licenses/by-nd/3.0/tw/)；保留完整原字库，不修改、转换或子集化，见 [本地授权说明](fonts/moe-lishu-LICENSE.md) |
| 鏡原甲骨文 Oracular | [官方字库网站](https://oracular.azurewebsites.net/glyphs/download)，Peichao Qin | 原项目字体说明记载 OFL 1.1，但当前仓库未附此字体的完整许可副本及版本来源凭据，仍需补齐核验 |
| 峄山碑篆体 | 旧页面标注“字传” | 当前仓库未附可核实的作者授权文件；不能仅凭“免费商用”标签推定可转换或随仓库再分发 |
| 说文小篆 | 旧页面标注“开元小篆 + 全字库说文解字” | 当前文件的组成、生成过程及对应许可未完整留档，不能直接套用候选上游的许可 |
| 崇羲篆体 | [中央研究院小學堂](https://xiaoxue.iis.sinica.edu.tw/chongxi/)；本地留有字体文件，当前页面未引用 | [CC BY-ND 3.0 TW 或后续版本](https://xiaoxue.iis.sinica.edu.tw/chongxi/copyright.htm)；本地文件的原版一致性及署名材料仍需核对，不能将其视为可改造字体 |
| Hanzi Writer 3.7.0 | [chanind/hanzi-writer](https://github.com/chanind/hanzi-writer) | [MIT](assets/hanzi-writer/LICENSE)；笔顺展示组件 |
| Hanzi Writer Data 2.0.1 | [chanind/hanzi-writer-data](https://github.com/chanind/hanzi-writer-data)，源自 [Make Me a Hanzi](https://github.com/skishore/makemeahanzi) / Arphic Technology Co., Ltd. | [Arphic Public License](assets/hanzi-writer-data/ARPHICPL.TXT)，与组件的 MIT 许可不同 |

已固定的包版本和本地资源哈希记录在 assets/offline-manifest.json。
更多字体说明见 [字体与授权](fonts/README.md)，笔顺资源说明见 [离线资源](assets/README.md)。

## 使用与再分发说明

本仓库公开展示不代表所有第三方资源采用同一开源许可。代码、字体、字典数据和古籍材料应分别按各自条款使用，
并保留作者署名、版权声明、许可文本及必要的改编说明。本 README 不是对所有资源的统一授权。

上述部分资源的来源和再分发授权尚未核实，不能据此承诺整个资源包可以任意商用、转换或再分发。
补写来源与免责声明不能替代授权；相关资源在进一步公开分发前应补齐凭据，或改用来源、许可清楚的替代资源。

如果发现署名、出处、许可或内容存在问题，请通过仓库 Issue 提供对应文件、来源链接及权利依据，以便核实、更正或移除。

## 开发与维护

本地运行、目录结构、离线资源维护和服务器发布说明已移至 [开发与维护文档](DEVELOPMENT.md)。
