# 第三方数据许可与署名

本目录保存数据来源的许可文本副本，随网站静态资源一起发布。项目介绍及完整来源清单见仓库根目录的 README。
资源保留各自许可；本目录不是对整个网站或全部字体的统一授权。

| 资源 | 上游与署名 | 许可副本 | 在本项目中的处理 |
| --- | --- | --- | --- |
| Unicode Unihan | [Unicode, Inc.](https://www.unicode.org/reports/tr38/)，本地数据头为 Unicode 18.0.0 | [Unicode License V3](Unicode-LICENSE.txt)，[官方原文](https://www.unicode.org/license.txt) | 提取读音、部首、繁简及变体字段，生成查询数据 |
| OpenCC | [BYVoid / OpenCC 贡献者](https://github.com/BYVoid/OpenCC) | [Apache-2.0](OpenCC-LICENSE.txt)，[上游原文](https://github.com/BYVoid/OpenCC/blob/master/LICENSE) | 提取单字对应关系，合并到查询索引；属于经过整理的数据 |
| 漢語拆字字典 | [開放詞典](https://github.com/kfcd/chaizi)，© 2015 開放詞典 | [上游许可说明](Chaizi-LICENSE.txt)，[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) | 整理简繁拆字及繁简索引，生成部件查询和反查数据 |
| 《汉语拼音辞典》 | [码谱 / mapull](https://github.com/mapull/chinese-dictionary)，© 2021 码谱 | [MIT](ChineseDictionary-LICENSE.txt)，[上游原文](https://github.com/mapull/chinese-dictionary/blob/main/LICENSE) | 提取字段、截取释义和书证；本地版本出处及原始辞书材料的权利仍待核实 |
| CC-CEDICT | [CC-CEDICT 贡献者 / MDBG](https://www.mdbg.net/chinese/dictionary?page=cc-cedict)；CEDICT 由 Paul Andrew Denisowski 于 1997 年发起 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)（与本地原始数据头一致） | 筛选词条、转换拼音声调、合并读音并生成 words/ 分片与字级繁简关系；对应改编数据按同一许可提供 |

以上许可文本于 2026-10-21 从所列官方链接保存，未修改正文。它们不证明缺少下载记录的本地材料与上游特定版本相同。
作者或机构名称仅用于署名，不表示其为本项目背书。

`assets/variant-index.json` 从本地 Unicode Unihan 和现有主字库、扩展字库生成，新增原字部首、总笔画、部外笔画及直接对应关系，
不按是否有读音筛除字符。每条关系保留来源，语义关系标为参考；沿用以上各来源的数据许可。

`assets/radical-strokes.js` 整理现代部首自身的笔画，使用现有主字库、《汉语拼音辞典》和 Unihan；
符号区偏旁按 [Unicode 18.0 等价汉字映射](https://www.unicode.org/Public/18.0.0/ucd/EquivalentUnifiedIdeograph.txt) 补齐。

## 其他资源

- [Hanzi Writer](../hanzi-writer/README.md) 采用 [MIT](../hanzi-writer/LICENSE)。
- [Hanzi Writer Data](../hanzi-writer-data/README.md) 源自 Make Me a Hanzi / Arphic Technology Co., Ltd.，采用 [Arphic Public License](../hanzi-writer-data/ARPHICPL.TXT)。
- 网页字体的作者与许可见 [字体说明](../../fonts/README.md) 及各字体目录的许可文件；教育部隶书署名为「中華民國教育部」，许可为 CC BY-ND 3.0 TW。
- gsc_pinyin.csv 的具体来源、部分辞书原始材料的再分发权利，以及甲骨文、峄山碑、说文小篆等本地字体的完整版本授权凭据仍待补齐。仓库包含文件、网站能够显示字形，均不等于已确认再分发许可。

如发现来源、署名或许可有误，请通过项目仓库 Issue 提供对应资源、出处与权利依据，便于核实和处理。
