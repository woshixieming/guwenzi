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

## 异体字查找

“异体字查找”支持按原字部首、总笔画或部外笔画筛选，并提供可选部件筛选、相邻笔画范围和分页。
默认只列出有对应或参考关系的字；取消勾选后可查阅更大的 Unihan 字库，包含没有读音或没有对应规范字的字符。
字形由本地字体及系统字体显示，部分扩展字可能缺字；结果保留字符复制和 Unicode 编码，不能把方框当作字形依据。

检索数据按需从 `assets/variant-index.json` 加载，不增加首页初次加载的字库体积。
它由现有主字库、扩展字库和本地 `data/Unihan.zip` 生成，不修改 `data.js` 或 `data_ext.js`：

```bash
python3 scripts/build_variant_index.py
```

更新上述输入后应重新生成索引。按原字自身的部首和笔画建索引，不从对应简体字借用笔画。
匹配关系保留来源和多个候选；语义关系只作参考，不做传递转换。
智能查询复用该反查结果；家谱转写仅对表外字采用唯一明确候选，歧义、仅语义关联和本身属于规范字的写法保留原文。
部件数据覆盖有限，添加部件条件可能排除尚无拆字记录的字。

## 截图识字与 OpenAI 兼容接口

选图、粘贴截图、拖动框选和选区滑块均在浏览器内完成。只有点击“识别选区”才发送选区图片，
不会自动上传整页图像，不在浏览器或服务端磁盘保存图片。模型候选必须经用户点击确认，再进入本地规范字反查；
模型不负责确定规范字对应关系。换图、调整选区、取消或切换页面入口会忽略旧识别结果。

普通静态服务器继续支持部首查字和图片裁剪，但没有 OCR 接口时会显示服务不可用/暂未配置。
可选服务 `server/ocr_server.py` 仅使用 Python 3.9+ 标准库，同时支持本地静态预览及 `/api/ocr` 接口：

```bash
python3 server/ocr_server.py --port 8000
```

不传配置时识字默认关闭；`GET /api/ocr/status` 仅返回是否完成配置，不返回密钥、服务地址或模型。
参数模板位于 `server/ocr-config.example.json`，预留以下字段，实际连接信息后续填写：

| 字段 | 用途 |
| --- | --- |
| `enabled` | 默认 false；准备启用时设为 true |
| `base_url` | OpenAI 兼容 API 根地址，包含版本前缀，例如 `https://api.openai.com/v1`；脚本追加 `/chat/completions` |
| `api_key` | 服务端 API 密钥，留空则不能发起识别 |
| `model` | 支持图像输入的模型标识，留空则不能发起识别 |
| `timeout_seconds` | 上游超时，默认 45 秒，允许 1–60 |
| `requests_per_minute` | TCP 来源每分钟请求上限，默认 6；全服务同时设有两倍此值的总上限和 2 个并发调用上限 |
| `allowed_origins` | 可选的浏览器来源列表；默认只接受与 Host 一致的同源请求，配置应包含协议和必要端口 |

将模板复制到**项目目录之外**的私有路径后填写，例如 `/etc/guwenzi/ocr.json`，不要修改模板来保存实际密钥，
不要提交配置或放进网站根目录。服务会拒绝读取项目目录内部的实际配置文件；它不自动读取 `.env`。

```bash
python3 server/ocr_server.py --config /etc/guwenzi/ocr.json --bind 127.0.0.1 --port 8010
```

请求使用 OpenAI Chat Completions 多模态格式：`messages` 中传入文本及 `image_url` base64 图片、
`response_format: {"type":"json_object"}`、`max_completion_tokens` 和 `detail: "high"`。
兼容服务及所选模型需支持这些参数，参见 [OpenAI 图像输入说明](https://developers.openai.com/api/docs/guides/images-vision)。
返回的 JSON 候选经过格式校验，只允许最多 5 个单个汉字；不对原字做兼容归一化或繁简转换。
识别准确率、模型对旧字形的覆盖及额度需配置后用实际样本验证。

### 线上接入

现有发布脚本继续只部署静态运行文件，新增 `assets/` 下的索引、脚本、样式会自动纳入增量发布。
OCR 服务及真实配置需单独部署、启动，静态上传不会启动 Python 进程，也不会更新它的配置。
建议将服务代码置于独立目录（例如 `/opt/guwenzi/server/`），真实配置置于 `/etc/guwenzi/`，
通过现有进程管理工具保持服务运行；由 Nginx 将同域 `/api/ocr` 和 `/api/ocr/status` 转发到本机服务。
保留 `Host` 请求头；若代理改变 Host，则在私有配置的 `allowed_origins` 中填写实际网站来源。
Nginx 的请求体限制需至少 6 MiB、读取超时需大于上游超时，其他路径继续作为静态文件提供。

服务不向客户端接受模型、API 地址或 API 密钥，拒绝跨来源请求、远程图片 URL 和上游重定向；
限制请求体和响应体大小，不记录图片或上游错误正文。配置留空时不会调用任何外部模型。
来源校验不是用户鉴权；如将付费识别向公网开放，应在现有网关按业务需要配置访问控制和总调用额度。
服务不信任客户端提交的转发 IP 头；通过本机反向代理时，来自代理的请求共享该来源的频率限制。

## 针对性验证

```bash
node tests/variant-core.test.cjs
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/build_variant_index.py --check
python3 scripts/sync_offline_assets.py --check
bash -n scripts/deploy-artifact.sh
```

后端测试使用本地模拟 OpenAI 服务，不使用真实密钥、不调用外部模型。
页面检查可通过可选 Python 服务运行，验证部首筛选、多个候选、截图裁剪、未配置提示和家谱歧义保留。
