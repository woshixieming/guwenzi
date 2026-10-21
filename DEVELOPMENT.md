# 开发与维护

项目介绍及第三方资源来源见 [README](README.md)。本文集中说明本地运行、数据维护与发布流程。

## 本地启动

需要 Python 3。在项目根目录执行：

```bash
python3 -m http.server 8000 --bind 127.0.0.1
```

浏览器访问 <http://127.0.0.1:8000/>。

项目已包含运行所需的生成数据，无需重新构建字库。
书法字体、笔顺组件及完整笔顺数据均已随项目保存，启动本地服务后无需访问外部 CDN。
页面中的来源和授权链接供主动查阅，离线时不影响查字与笔顺动画。
请通过上述 HTTP 服务访问，直接双击 HTML 文件可能使浏览器拦截本地数据请求。

## 目录

- `index.html`：页面、样式及交互逻辑。
- `data.js`、`data_ext.js`、`hwset.js`：主字库、扩展字库与笔顺收字表。
- `defs/`、`words/`：按需加载的字义和词语分片。
- `fonts/`：本地字体、覆盖表及来源与授权说明。
- `assets/`：本地笔顺组件、笔顺数据、资源校验清单及第三方说明。
- `data/`：构建字库所用的原始数据。
- `scripts/`：数据生成、资源维护及服务器发布脚本。

字体来源、覆盖规则及授权信息见 [字体说明](fonts/README.md)。
其他数据来源及署名见页面页脚。

## 离线资源维护

克隆项目后可检查资源完整性，此命令不访问网络：

```bash
python3 scripts/sync_offline_assets.py --check
```

需要重新下载离线资源时运行以下命令（需联网，保留当前固定版本）：

```bash
python3 scripts/sync_offline_assets.py
```

第三方版本、来源和许可证见 [离线资源说明](assets/README.md)。

## 发布到服务器

发布或远端预览时，脚本会依次要求输入服务器 IP/域名、SSH 端口和用户名。
三个连接参数没有默认值，不从环境变量读取，也不保存到文件。
`--dry-run` 只执行本地检查，不询问连接参数。

```bash
./scripts/deploy-artifact.sh --dry-run  # 仅本地校验，不连接服务器
./scripts/deploy-artifact.sh --preview  # 连接服务器，预览需要同步的文件，不修改远端文件
./scripts/deploy-artifact.sh            # 正式增量发布
```

可从任意工作目录运行脚本。需要本地 Python 3（资源校验）、rsync、SSH，以及服务器 SSH 访问权限；
服务器需要 Bash、rsync、find，并已通过宝塔或 Nginx 将域名指向上述网站根目录。
本项目无需 npm 构建、数据库或 PM2，不需要重启 Web 服务。

默认不生成全量包，通过 rsync 比较文件内容，只传输新增或变化的文件。
字体和笔顺资源没有变化时会跳过，有更新时自动同步，无需手动区分资源发布。
每次比较会读取两端文件计算校验和，但不会因相同内容的文件修改时间不同而重复上传。
资源同步成功后，最后同步 `index.html`；显示变化文件、文件上传进度和每阶段的传输统计。
兼容 macOS 自带的旧版 rsync/openrsync，不传输 macOS 扩展属性或 ACL。

脚本只上传页面、字库、字义/词语分片、字体和笔顺资源，不上传 `.env`、Git、原始 `data/` 或维护脚本。
增量发布只将被覆盖文件的旧版本备份至 `<网站根目录>.backups/<发布编号>/`，
保留原目录结构；该目录是本次变更的旧文件集合，并非完整网站快照。
未变化的资源不重复备份，无覆盖时备份目录为空。历史备份不会自动清理。
不启用自动删除，服务器上其他文件、以及本地已移除的旧资源会继续保留。
发布不保证整个网站原子切换，中断可能留下部分已更新的资源；可重新执行脚本补齐，建议避开访问高峰。

服务器没有 rsync，或需要全量发布时，仍可使用原打包方式（两端需要 tar，本地需要 SCP）：

```bash
./scripts/deploy-artifact.sh --full --dry-run  # 仅本地校验、打包
./scripts/deploy-artifact.sh --full            # 全量发布
```

全量模式显示包大小（MiB 和字节数）及 SCP 上传进度，非终端输出环境通过 Python 3 保留进度。
打包时排除 macOS 扩展属性和 ACL，避免 Linux 解包时出现 `LIBARCHIVE.xattr.com.apple.quarantine` 等警告。
全量模式会将已有的对应文件/目录整体备份为备份根目录下的 `.tar.gz` 文件。

目标目录和备份目录仍通过 `DEPLOY_PATH`、`BACKUP_PATH` 环境变量设置，连接信息在终端中输入。
不需要新增或提交本地配置文件；密码与密钥口令由 SSH 自行处理。没有交互式终端时，正式发布和远端预览会报错退出。
例如指定自己的站点目录：

```bash
DEPLOY_PATH=/www/wwwroot/example.org ./scripts/deploy-artifact.sh
```

未设置 `DEPLOY_PATH` 时使用脚本内现有的网站目录。`BACKUP_PATH` 默认为 `${DEPLOY_PATH}.backups`，且必须位于网站目录之外。
更多选项见 `./scripts/deploy-artifact.sh --help`。
需要发布后检查公网访问时执行：

```bash
HEALTH_URL=https://example.org/ ./scripts/deploy-artifact.sh
```

HTTP 检查失败会返回非零状态，但不会自动回滚已上传的文件；预览模式不执行 HTTP 检查。
