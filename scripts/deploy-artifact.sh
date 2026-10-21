#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_USER="${DEPLOY_USER:-root}"
DEPLOY_HOST="${DEPLOY_HOST:-150.158.45.203}"
DEPLOY_PORT="${DEPLOY_PORT:-520}"
DEPLOY_PATH="${DEPLOY_PATH:-/www/wwwroot/character.xm4021.com}"
BACKUP_PATH="${BACKUP_PATH:-${DEPLOY_PATH}.backups}"
HEALTH_URL="${HEALTH_URL:-}"
RUN_CHECK="${RUN_CHECK:-1}"
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage:
  ./scripts/deploy-artifact.sh             校验、打包并发布静态网站
  ./scripts/deploy-artifact.sh --dry-run   仅校验、打包，不连接服务器

Environment:
  DEPLOY_USER   SSH 用户，默认 root
  DEPLOY_HOST   服务器 IP，默认 150.158.45.203
  DEPLOY_PORT   SSH 端口，默认 520
  DEPLOY_PATH   网站根目录，默认 /www/wwwroot/character.xm4021.com
  BACKUP_PATH   备份目录，默认 ${DEPLOY_PATH}.backups（必须在网站目录外）
  HEALTH_URL    可选的发布后 HTTP 检查地址，例如 https://character.xm4021.com/
  RUN_CHECK=0   跳过本地离线资源完整性校验

Notes:
  使用 SSH 密钥或交互式认证，不在脚本中保存密码。
  打包后显示包大小；上传时显示 SCP 百分比、速度和预计剩余时间。
  非终端输出环境通过 Python 3 保留 SCP 进度显示。
  仅上传运行资源，不上传 .env、Git、原始 data/ 或维护脚本。
  覆盖前备份已有的同名文件/目录，不删除服务器上其他文件。
  无需 Node.js、数据库、PM2 或重启 Web 服务。
EOF
}

log() { printf '[deploy] %s\n' "$*"; }
fail() { printf '[deploy] ERROR: %s\n' "$*" >&2; exit 1; }

case "${1:-}" in
  '') ;;
  --dry-run) DRY_RUN=1 ;;
  -h|--help) usage; exit 0 ;;
  *) usage; fail "未知参数：$1" ;;
esac
[[ $# -le 1 ]] || fail "参数过多。"

# 限制远端参数字符，避免 SSH 的远端 shell 将路径解释为命令。
[[ "$DEPLOY_USER" =~ ^[a-zA-Z0-9_][a-zA-Z0-9_-]*$ ]] || fail "无效的 SSH 用户。"
[[ "$DEPLOY_HOST" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]] || fail "无效的服务器地址。"
[[ "$DEPLOY_PORT" =~ ^[0-9]{1,5}$ ]] || fail "无效的 SSH 端口。"
[[ $((10#$DEPLOY_PORT)) -ge 1 && $((10#$DEPLOY_PORT)) -le 65535 ]] || fail "SSH 端口超出范围。"
[[ "$RUN_CHECK" == 0 || "$RUN_CHECK" == 1 ]] || fail "RUN_CHECK 只能为 0 或 1。"
for path in "$DEPLOY_PATH" "$BACKUP_PATH"; do
  [[ "$path" =~ ^/[a-zA-Z0-9._/-]+$ && "$path" != *'//'* && "$path" != */ ]] || fail "请使用无空格的绝对目录路径，且不以 / 结尾。"
  [[ "$path/" != *'/../'* && "$path/" != *'/./'* ]] || fail "目录不能含 . 或 .. 路径段。"
done
[[ "$BACKUP_PATH/" != "$DEPLOY_PATH/"* ]] || fail "备份目录必须在网站目录外。"

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
for tool in tar mktemp; do
  command -v "$tool" >/dev/null 2>&1 || fail "缺少命令：$tool"
done
if [[ "$DRY_RUN" == 0 ]]; then
  for tool in ssh scp; do
    command -v "$tool" >/dev/null 2>&1 || fail "缺少命令：$tool"
  done
  if [[ ! -t 1 || ! -t 2 ]]; then
    command -v python3 >/dev/null 2>&1 || fail "非终端环境显示上传进度需要 Python 3。"
  fi
  if [[ -n "$HEALTH_URL" ]]; then
    command -v curl >/dev/null 2>&1 || fail "缺少命令：curl"
  fi
fi

FILES=(data.js data_ext.js hwset.js defs words fonts assets index.html)
for file in "${FILES[@]}"; do
  [[ -e "$file" ]] || fail "运行资源缺失：$file"
done
if [[ "$RUN_CHECK" == 1 ]]; then
  command -v python3 >/dev/null 2>&1 || fail "资源校验需要 Python 3。"
  log "校验离线资源"
  python3 scripts/sync_offline_assets.py --check
fi

ARTIFACT_PATH="$(mktemp "${TMPDIR:-/tmp}/guwenzi-$(date +%Y%m%d%H%M%S).XXXXXX")"
trap 'rm -f -- "$ARTIFACT_PATH"' EXIT
RELEASE_ID="${ARTIFACT_PATH##*/}"
REMOTE_ARTIFACT="/tmp/${RELEASE_ID}.tar.gz"
REMOTE="${DEPLOY_USER}@${DEPLOY_HOST}"

log "打包静态资源"
# COPYFILE_DISABLE 只处理 AppleDouble，仍需显式禁用 pax 扩展属性。
TAR_METADATA_ARGS=(--no-xattrs --no-acls)
if [[ "$(tar --version)" == *bsdtar* ]]; then
  TAR_METADATA_ARGS+=(--no-fflags)
  if [[ "$(uname -s)" == Darwin ]]; then
    TAR_METADATA_ARGS+=(--no-mac-metadata)
  fi
fi
COPYFILE_DISABLE=1 tar "${TAR_METADATA_ARGS[@]}" --exclude='.DS_Store' --exclude='._*' \
  --exclude='.env' --exclude='.env.*' --exclude='.git' \
  -czf "$ARTIFACT_PATH" "${FILES[@]}"
ARTIFACT_BYTES="$(wc -c < "$ARTIFACT_PATH")"
ARTIFACT_BYTES="$((ARTIFACT_BYTES))"
ARTIFACT_SIZE="$(awk -v bytes="$ARTIFACT_BYTES" 'BEGIN { printf "%.2f MiB", bytes / 1048576 }')"
log "发布包大小：${ARTIFACT_SIZE}（${ARTIFACT_BYTES} 字节）"
if [[ "$DRY_RUN" == 1 ]]; then
  log "打包成功，目标 ${REMOTE}:${DEPLOY_PORT}${DEPLOY_PATH}；未连接服务器，临时包将在退出时清理。"
  exit 0
fi

log "上传到 ${REMOTE}:${DEPLOY_PATH}（端口 ${DEPLOY_PORT}）"
SCP_COMMAND=(scp -P "$DEPLOY_PORT" -o ConnectTimeout=15 -o LogLevel=INFO "$ARTIFACT_PATH" "${REMOTE}:${REMOTE_ARTIFACT}")
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

if [[ -n "$HEALTH_URL" ]]; then
  log "检查 ${HEALTH_URL}"
  curl --fail --show-error --silent --location --connect-timeout 10 --max-time 30 "$HEALTH_URL" >/dev/null
fi
log "发布完成"
