# 本地离线资源

页面运行时从本地读取以下资源，不依赖外部 CDN。
数据和组件保持原有固定版本，字体文件未修改。

| 资源 | 版本 | 路径 | 许可 |
| --- | --- | --- | --- |
| Hanzi Writer | 3.7.0 | `hanzi-writer/hanzi-writer.min.js` | MIT，见同目录 `LICENSE` |
| Hanzi Writer Data | 2.0.1 | `hanzi-writer-data/` | Arphic Public License，见 `ARPHICPL.TXT` 及 `APL/` |
| 网页书法字体 | 见字体说明 | `../fonts/web/` | SIL OFL 1.1，见各目录许可文件 |

- Hanzi Writer：https://github.com/chanind/hanzi-writer
- Hanzi Writer Data：https://github.com/chanind/hanzi-writer-data
- 笔顺数据源自 Make Me a Hanzi：https://github.com/skishore/makemeahanzi
- 原字体版权方：Arphic Technology Co., Ltd.（文鼎科技）；数据署名及许可说明保存在原包的 README 和授权文件中。
- 字体来源与版本：[字体说明](../fonts/README.md)。

`offline-manifest.json` 记录 npm 下载地址、固定版本、包完整性信息及每个本地文件的大小和 SHA-256。
额外补存的字体许可证来源地址亦记录在其中。

离线校验：

```bash
python3 scripts/sync_offline_assets.py --check
```

重新下载（需联网）：

```bash
python3 scripts/sync_offline_assets.py
```

下载脚本只保存页面使用的 WOFF2 字体源及相应 CSS、组件、笔顺 JSON 和授权文件，
不运行 npm 安装脚本，也不要求运行网站的电脑安装 Node.js。
