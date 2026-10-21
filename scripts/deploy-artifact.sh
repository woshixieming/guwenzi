#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_USER=""
DEPLOY_HOST=""
DEPLOY_PORT=""
DEPLOY_PATH="${DEPLOY_PATH:-/www/wwwroot/character.xm4021.com}"
BACKUP_PATH="${BACKUP_PATH:-${DEPLOY_PATH}.backups}"
HEALTH_URL="${HEALTH_URL:-}"
RUN_CHECK="${RUN_CHECK:-1}"
DRY_RUN=0
FULL=0
PREVIEW=0
WITH_OCR=0
OCR_ONLY=0
OCR_DEPLOY_PATH="${OCR_DEPLOY_PATH:-/opt/guwenzi-ocr}"
OCR_CONFIG_PATH="${OCR_CONFIG_PATH:-/etc/guwenzi/ocr.json}"
OCR_SERVICE_NAME="${OCR_SERVICE_NAME:-guwenzi-ocr}"
OCR_PORT="${OCR_PORT:-8010}"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/deploy-artifact.sh             校验并增量发布（默认）
  ./scripts/deploy-artifact.sh --dry-run   仅本地校验，不连接服务器
  ./scripts/deploy-artifact.sh --preview   连接服务器预览增量变化，不修改远端文件
  ./scripts/deploy-artifact.sh --full      全量打包、上传并发布
  ./scripts/deploy-artifact.sh --full --dry-run  仅校验、打包，不连接服务器
  ./scripts/deploy-artifact.sh --with-ocr  部署 OCR 后端，然后增量发布网站
  ./scripts/deploy-artifact.sh --ocr-only  仅部署并重启 OCR 后端
  --with-ocr / --ocr-only 可与 --dry-run 或 --preview 组合使用

Environment:
  DEPLOY_PATH   网站根目录，默认 /www/wwwroot/character.xm4021.com
  BACKUP_PATH   备份目录，默认 ${DEPLOY_PATH}.backups（必须在网站目录外）
  HEALTH_URL    可选的发布后 HTTP 检查地址，例如 https://character.xm4021.com/
  RUN_CHECK=0   跳过本地离线资源完整性校验
  OCR_DEPLOY_PATH   后端专用目录，默认 /opt/guwenzi-ocr（网站目录之外）
  OCR_CONFIG_PATH   私有配置路径，默认 /etc/guwenzi/ocr.json（代码和网站目录之外）
  OCR_SERVICE_NAME  systemd 服务名，默认 guwenzi-ocr
  OCR_PORT          后端本机监听端口，默认 8010

Notes:
  发布和远端预览时在终端输入服务器 IP/域名、SSH 端口和用户名，无默认值。
  连接参数只用于本次执行，不写入文件；--dry-run 不需要输入连接参数。
  使用 SSH 密钥或交互式认证，不在脚本中保存密码。
  增量模式需要两端安装 rsync，按内容校验跳过未变化的文件。
  显示变化文件、上传进度和传输统计；资源同步成功后才更新首页。
  全量模式显示包大小和 SCP 进度；非终端输出需要 Python 3。
  仅上传运行资源，不上传 .env、Git、原始 data/ 或维护脚本。
  增量模式只备份被覆盖的文件；全量模式备份已有的同名文件/目录。
  不自动删除服务器上其他文件，也不自动清理历史备份。
  默认仅发布静态网站。OCR 部署需要远端 Python 3.9+、systemd 和 root/免交互 sudo 权限。
  OCR 使用专用受限账号运行；首次生成关闭状态的配置，后续保留已有配置内容。
  不自动修改 Nginx，反向代理示例见 DEVELOPMENT.md。无需 Node.js、数据库或 PM2。
EOF
}

log() { printf '[deploy] %s\n' "$*"; }
fail() { printf '[deploy] ERROR: %s\n' "$*" >&2; exit 1; }

for argument in "$@"; do
  case "$argument" in
    --dry-run) DRY_RUN=1 ;;
    --full) FULL=1 ;;
    --preview) PREVIEW=1 ;;
    --with-ocr) WITH_OCR=1 ;;
    --ocr-only) WITH_OCR=1; OCR_ONLY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; fail "未知参数：$argument" ;;
  esac
done
[[ "$PREVIEW" == 0 || ( "$FULL" == 0 && "$DRY_RUN" == 0 ) ]] || fail "--preview 不能与 --full 或 --dry-run 一起使用。"

[[ "$OCR_ONLY" == 0 || "$FULL" == 0 ]] || fail "--ocr-only 不能与 --full 一起使用。"
if [[ "$WITH_OCR" == 1 ]]; then
  [[ "$OCR_SERVICE_NAME" =~ ^[a-zA-Z][a-zA-Z0-9_-]*$ ]] || fail "无效的 OCR 服务名。"
  [[ "$OCR_PORT" =~ ^[0-9]{1,5}$ ]] || fail "无效的 OCR 端口。"
  [[ $((10#$OCR_PORT)) -ge 1024 && $((10#$OCR_PORT)) -le 65535 ]] || fail "OCR 端口需在 1024–65535 之间。"
  for path in "$OCR_DEPLOY_PATH" "$OCR_CONFIG_PATH"; do
    [[ "$path" =~ ^/[a-zA-Z0-9._/-]+$ && "$path" != *'//'* && "$path" != */ ]] || fail "OCR 代码和配置需使用无空格的绝对路径。"
    [[ "$path/" != *'/../'* && "$path/" != *'/./'* ]] || fail "OCR 路径不能含 . 或 .. 路径段。"
  done
  [[ "$OCR_DEPLOY_PATH/" != "$DEPLOY_PATH/"* && "$DEPLOY_PATH/" != "$OCR_DEPLOY_PATH/"* ]] || fail "OCR 代码必须位于独立的网站外目录。"
  [[ "$OCR_CONFIG_PATH/" != "$DEPLOY_PATH/"* && "$OCR_CONFIG_PATH/" != "$OCR_DEPLOY_PATH/"* ]] || fail "私有配置必须位于网站和 OCR 代码之外。"
fi
[[ "$RUN_CHECK" == 0 || "$RUN_CHECK" == 1 ]] || fail "RUN_CHECK 只能为 0 或 1。"
for path in "$DEPLOY_PATH" "$BACKUP_PATH"; do
  [[ "$path" =~ ^/[a-zA-Z0-9._/-]+$ && "$path" != *'//'* && "$path" != */ ]] || fail "请使用无空格的绝对目录路径，且不以 / 结尾。"
  [[ "$path/" != *'/../'* && "$path/" != *'/./'* ]] || fail "目录不能含 . 或 .. 路径段。"
done
[[ "$BACKUP_PATH/" != "$DEPLOY_PATH/"* ]] || fail "备份目录必须在网站目录外。"

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
command -v mktemp >/dev/null 2>&1 || fail "缺少命令：mktemp"
if [[ "$FULL" == 1 || "$WITH_OCR" == 1 ]]; then
  command -v tar >/dev/null 2>&1 || fail "缺少命令：tar"
fi
if [[ "$DRY_RUN" == 0 ]]; then
  command -v ssh >/dev/null 2>&1 || fail "缺少命令：ssh"
  if [[ "$FULL" == 1 || "$WITH_OCR" == 1 ]]; then
    command -v scp >/dev/null 2>&1 || fail "缺少命令：scp"
    if [[ ! -t 1 || ! -t 2 ]]; then
      command -v python3 >/dev/null 2>&1 || fail "非终端环境显示上传进度需要 Python 3。"
    fi
  fi
  if [[ "$FULL" == 0 && "$OCR_ONLY" == 0 ]]; then
    command -v rsync >/dev/null 2>&1 || fail "增量发布需要本地安装 rsync。"
  fi
  if [[ "$OCR_ONLY" == 0 && "$PREVIEW" == 0 && -n "$HEALTH_URL" ]]; then
    command -v curl >/dev/null 2>&1 || fail "缺少命令：curl"
  fi
fi

RESOURCES=(data.js data_ext.js hwset.js defs words fonts assets)
FILES=("${RESOURCES[@]}" index.html)
if [[ "$OCR_ONLY" == 0 ]]; then
  for file in "${FILES[@]}"; do
    [[ -e "$file" ]] || fail "运行资源缺失：$file"
  done
  [[ -s index.html ]] || fail "首页 index.html 为空。"
  [[ -z "$(find "${FILES[@]}" -type l -print -quit)" ]] || fail "本地运行资源包含符号链接，请先人工检查。"
  if [[ "$RUN_CHECK" == 1 ]]; then
    command -v python3 >/dev/null 2>&1 || fail "资源校验需要 Python 3。"
    log "校验离线资源"
    python3 scripts/sync_offline_assets.py --check
  fi
fi
if [[ "$WITH_OCR" == 1 ]]; then
  command -v python3 >/dev/null 2>&1 || fail "校验 OCR 代码需要本地 Python 3。"
  [[ -f scripts/deploy-ocr-remote.sh && -f server/ocr_server.py && -f server/ocr-config.example.json ]] || fail "OCR 部署源文件缺失。"
  [[ ! -L server/ocr_server.py && ! -L server/ocr-config.example.json && ! -L scripts/deploy-ocr-remote.sh ]] || fail "OCR 部署源文件不能是符号链接。"
  bash -n scripts/deploy-ocr-remote.sh
  python3 - <<'PY_CHECK'
import ast, json
from pathlib import Path
ast.parse(Path('server/ocr_server.py').read_text(encoding='utf-8'))
config = json.loads(Path('server/ocr-config.example.json').read_text(encoding='utf-8'))
if config.get('enabled') is not False or config.get('api_key') or config.get('model'):
    raise SystemExit('发布模板必须关闭 OCR 且不含密钥或模型；请在服务器私有配置中填写。')
PY_CHECK
fi

if [[ "$DRY_RUN" == 0 ]]; then
  # 从控制终端读取，避免连接参数与后续 SSH/rsync 的标准输入混在一起。
  if ! { exec 3<> /dev/tty; } 2>/dev/null; then
    fail "请在交互式终端运行，以输入服务器地址、端口和用户名；本地检查可使用 --dry-run。"
  fi
  read -r -p "服务器 IP 或域名：" DEPLOY_HOST <&3 || fail "未读取到服务器地址。"
  read -r -p "SSH 端口：" DEPLOY_PORT <&3 || fail "未读取到 SSH 端口。"
  read -r -p "SSH 用户名：" DEPLOY_USER <&3 || fail "未读取到 SSH 用户名。"
  exec 3>&-

  # 限制远端参数字符，避免 SSH 的远端 shell 将输入解释为命令。
  [[ "$DEPLOY_USER" =~ ^[a-zA-Z0-9_][a-zA-Z0-9_-]*$ ]] || fail "无效的 SSH 用户。"
  [[ "$DEPLOY_HOST" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]] || fail "无效的服务器地址。"
  [[ "$DEPLOY_PORT" =~ ^[0-9]{1,5}$ ]] || fail "无效的 SSH 端口。"
  [[ $((10#$DEPLOY_PORT)) -ge 1 && $((10#$DEPLOY_PORT)) -le 65535 ]] || fail "SSH 端口超出范围。"
fi

ARTIFACT_PATH="$(mktemp "${TMPDIR:-/tmp}/guwenzi-$(date +%Y%m%d%H%M%S).XXXXXX")"
OCR_ARTIFACT_PATH=""
cleanup() {
  rm -f -- "$ARTIFACT_PATH"
  [[ -z "$OCR_ARTIFACT_PATH" ]] || rm -f -- "$OCR_ARTIFACT_PATH"
}
trap cleanup EXIT
RELEASE_ID="${ARTIFACT_PATH##*/}"
REMOTE_ARTIFACT="/tmp/${RELEASE_ID}.tar.gz"
REMOTE="${DEPLOY_USER}@${DEPLOY_HOST}"

# COPYFILE_DISABLE 只处理 AppleDouble，仍需显式禁用 pax 扩展属性。
TAR_METADATA_ARGS=(--no-xattrs --no-acls)
if [[ ( "$FULL" == 1 || "$WITH_OCR" == 1 ) && "$(tar --version)" == *bsdtar* ]]; then
  TAR_METADATA_ARGS+=(--no-fflags)
  if [[ "$(uname -s)" == Darwin ]]; then
    TAR_METADATA_ARGS+=(--no-mac-metadata)
  fi
fi

upload_artifact() {
  SCP_COMMAND=(scp -P "$DEPLOY_PORT" -o ConnectTimeout=15 -o LogLevel=INFO "$1" "${REMOTE}:$2")
  if [[ -t 1 && -t 2 ]]; then
    "${SCP_COMMAND[@]}"
  else
    # SCP 在非 TTY 环境默认隐藏进度；伪终端保留原生进度及认证交互。
    python3 -c '
import os
import pty
import sys

status = pty.spawn(sys.argv[1:])
sys.exit(os.waitstatus_to_exitcode(status))
' "${SCP_COMMAND[@]}"
  fi
}

run_ocr_remote() {
  # sudo 只用于明确选择的 OCR 部署；脚本通过 stdin 传入，不传递私有配置内容。
  ssh -p "$DEPLOY_PORT" -o ConnectTimeout=15 "$REMOTE" \
    "if [ \"\$(id -u)\" = 0 ]; then bash -s -- '$1' '$DEPLOY_PATH' '$OCR_DEPLOY_PATH' '$OCR_CONFIG_PATH' '$OCR_SERVICE_NAME' '$OCR_PORT' '$RELEASE_ID' '$REMOTE_OCR_ARTIFACT'; else sudo -n bash -s -- '$1' '$DEPLOY_PATH' '$OCR_DEPLOY_PATH' '$OCR_CONFIG_PATH' '$OCR_SERVICE_NAME' '$OCR_PORT' '$RELEASE_ID' '$REMOTE_OCR_ARTIFACT'; fi" \
    < scripts/deploy-ocr-remote.sh
}

deploy_ocr() {
  if [[ "$DRY_RUN" == 1 ]]; then
    log "OCR 代码、模板与远端部署脚本校验通过；目标 ${OCR_DEPLOY_PATH}，服务 ${OCR_SERVICE_NAME}，未连接服务器。"
    return
  fi
  REMOTE_OCR_ARTIFACT="/tmp/${RELEASE_ID}.ocr.tar.gz"
  if [[ "$PREVIEW" == 1 ]]; then run_ocr_remote preview; return; fi
  run_ocr_remote check
  OCR_ARTIFACT_PATH="$(mktemp "${TMPDIR:-/tmp}/guwenzi-ocr.XXXXXX")"
  COPYFILE_DISABLE=1 tar "${TAR_METADATA_ARGS[@]}" -czf "$OCR_ARTIFACT_PATH" server/ocr_server.py server/ocr-config.example.json
  log "OCR 后端发布包：$(wc -c < "$OCR_ARTIFACT_PATH" | tr -d ' ') 字节"
  upload_artifact "$OCR_ARTIFACT_PATH" "$REMOTE_OCR_ARTIFACT"
  run_ocr_remote install
}

check_health() {
  if [[ -n "$HEALTH_URL" ]]; then
    log "检查 ${HEALTH_URL}"
    curl --fail --show-error --silent --location --connect-timeout 10 --max-time 30 "$HEALTH_URL" >/dev/null
  fi
}

if [[ "$WITH_OCR" == 1 ]]; then
  deploy_ocr
  [[ "$OCR_ONLY" == 0 ]] || exit 0
fi

if [[ "$FULL" == 0 ]]; then
  if [[ "$DRY_RUN" == 1 ]]; then
    log "本地校验通过；默认使用 rsync 增量发布，不生成全量包。"
    log "未连接服务器；使用 --preview 可查看实际需要同步的文件。"
    exit 0
  fi

  log "检查远端 rsync 和目标资源路径"
  ssh -p "$DEPLOY_PORT" -o ConnectTimeout=15 "$REMOTE" \
    "bash -s -- '$DEPLOY_PATH' '$BACKUP_PATH' '$RELEASE_ID' '$PREVIEW'" <<'REMOTE_PREFLIGHT'
set -Eeuo pipefail
DEPLOY_PATH="$1"
BACKUP_PATH="$2"
RELEASE_ID="$3"
PREVIEW="$4"
command -v rsync >/dev/null 2>&1 || {
  printf '[remote] ERROR: 增量发布需要服务器安装 rsync；也可使用 --full 全量发布。\n' >&2
  exit 1
}
FILES=(data.js data_ext.js hwset.js defs words fonts assets index.html)
for file in "${FILES[@]}"; do
  if [[ -L "${DEPLOY_PATH}/${file}" ]] ||
    { [[ -d "${DEPLOY_PATH}/${file}" ]] && [[ -n "$(find "${DEPLOY_PATH}/${file}" -type l -print -quit)" ]]; }; then
    printf '[remote] ERROR: 目标资源包含符号链接，请先人工检查：%s\n' "$file" >&2
    exit 1
  fi
done
if [[ "$PREVIEW" == 0 ]]; then
  mkdir -p -- "$DEPLOY_PATH" "${BACKUP_PATH}/${RELEASE_ID}"
fi
REMOTE_PREFLIGHT

  # 使用旧版 rsync/openrsync 也支持的选项，不传输扩展属性或 ACL。
  RSYNC_ARGS=(--recursive --times --omit-dir-times --checksum
    --itemize-changes --human-readable --progress --stats
    --backup "--backup-dir=${BACKUP_PATH}/${RELEASE_ID}"
    --exclude='.DS_Store' --exclude='._*' --exclude='.env' --exclude='.env.*' --exclude='.git'
    -e "ssh -p ${DEPLOY_PORT} -o ConnectTimeout=15")
  if [[ "$PREVIEW" == 1 ]]; then
    RSYNC_ARGS+=(--dry-run)
    log "预览增量变化（不修改远端文件）"
  else
    log "按内容校验并增量上传到 ${REMOTE}:${DEPLOY_PATH}（端口 ${DEPLOY_PORT}）"
  fi

  log "同步字库、字体和笔顺等资源"
  COPYFILE_DISABLE=1 rsync "${RSYNC_ARGS[@]}" "${RESOURCES[@]}" "${REMOTE}:${DEPLOY_PATH}/"
  log "最后同步首页"
  COPYFILE_DISABLE=1 rsync "${RSYNC_ARGS[@]}" index.html "${REMOTE}:${DEPLOY_PATH}/"

  if [[ "$PREVIEW" == 1 ]]; then
    log "预览完成，未发布。"
    exit 0
  fi
  log "被覆盖文件的旧版本保存在 ${BACKUP_PATH}/${RELEASE_ID}/（无覆盖时目录为空）。"
  check_health
  log "增量发布完成"
  exit 0
fi

log "打包静态资源"
COPYFILE_DISABLE=1 tar "${TAR_METADATA_ARGS[@]}" --exclude='.DS_Store' --exclude='._*' \
  --exclude='.env' --exclude='.env.*' --exclude='.git' \
  -czf "$ARTIFACT_PATH" "${FILES[@]}"
ARTIFACT_BYTES="$(wc -c < "$ARTIFACT_PATH")"
ARTIFACT_BYTES="$((ARTIFACT_BYTES))"
ARTIFACT_SIZE="$(awk -v bytes="$ARTIFACT_BYTES" 'BEGIN { printf "%.2f MiB", bytes / 1048576 }')"
log "发布包大小：${ARTIFACT_SIZE}（${ARTIFACT_BYTES} 字节）"
if [[ "$DRY_RUN" == 1 ]]; then
  log "打包成功；未连接服务器，临时包将在退出时清理。"
  exit 0
fi

log "上传到 ${REMOTE}:${DEPLOY_PATH}（端口 ${DEPLOY_PORT}）"
upload_artifact "$ARTIFACT_PATH" "$REMOTE_ARTIFACT"
log "上传完成"
ssh -p "$DEPLOY_PORT" -o ConnectTimeout=15 "$REMOTE" \
  "bash -s -- '$DEPLOY_PATH' '$BACKUP_PATH' '$RELEASE_ID' '$REMOTE_ARTIFACT'" <<'REMOTE_SCRIPT'
set -Eeuo pipefail
DEPLOY_PATH="$1"
BACKUP_PATH="$2"
RELEASE_ID="$3"
REMOTE_ARTIFACT="$4"
trap 'rm -f -- "$REMOTE_ARTIFACT"' EXIT

FILES=(data.js data_ext.js hwset.js defs words fonts assets index.html)
mkdir -p -- "$DEPLOY_PATH" "$BACKUP_PATH"
# 避免解包通过已有符号链接写入网站目录之外。
for file in "${FILES[@]}"; do
  if [[ -L "${DEPLOY_PATH}/${file}" ]] ||
    { [[ -d "${DEPLOY_PATH}/${file}" ]] && [[ -n "$(find "${DEPLOY_PATH}/${file}" -type l -print -quit)" ]]; }; then
    printf '[remote] ERROR: 目标资源包含符号链接，请先人工检查：%s\n' "$file" >&2
    exit 1
  fi
done
tar -tzf "$REMOTE_ARTIFACT" >/dev/null
EXISTING=()
for file in "${FILES[@]}"; do
  [[ ! -e "${DEPLOY_PATH}/${file}" ]] || EXISTING+=("$file")
done
if [[ ${#EXISTING[@]} -gt 0 ]]; then
  tar -czf "${BACKUP_PATH}/${RELEASE_ID}.tar.gz" -C "$DEPLOY_PATH" "${EXISTING[@]}"
  printf '[remote] 已备份：%s/%s.tar.gz\n' "$BACKUP_PATH" "$RELEASE_ID"
fi
tar -xzf "$REMOTE_ARTIFACT" -C "$DEPLOY_PATH" --no-same-owner --no-same-permissions
[[ -s "${DEPLOY_PATH}/index.html" ]]
printf '[remote] 静态资源已发布到 %s\n' "$DEPLOY_PATH"
REMOTE_SCRIPT

check_health
log "发布完成"
