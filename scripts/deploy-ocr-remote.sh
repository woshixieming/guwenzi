#!/usr/bin/env bash
# 由 deploy-artifact.sh 经 SSH 标准输入执行，不单独保存连接信息。
set -Eeuo pipefail

MODE="$1"
WEB_ROOT="$2"
OCR_PATH="$3"
CONFIG_PATH="$4"
SERVICE="$5"
PORT="$6"
RELEASE_ID="$7"
ARTIFACT="$8"
UNIT_DIR="${OCR_SYSTEMD_DIR:-/etc/systemd/system}"
SERVICE_USER=guwenzi-ocr
UNIT_PATH="${UNIT_DIR}/${SERVICE}.service"
RELEASE_DIR="${OCR_PATH}/releases/${RELEASE_ID}"
CURRENT="${OCR_PATH}/current"
MARKER='# Managed by guwenzi OCR deployment'

log() { printf '[ocr] %s\n' "$*"; }
fail() { printf '[ocr] ERROR: %s\n' "$*" >&2; exit 1; }
[[ "$MODE" == check || "$MODE" == preview || "$MODE" == install ]] || fail "未知操作。"
[[ "$SERVICE" =~ ^[a-zA-Z][a-zA-Z0-9_-]*$ && "$RELEASE_ID" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]] || fail "无效的服务名或版本号。"
[[ "$PORT" =~ ^[0-9]{1,5}$ ]] || fail "无效的端口。"
[[ $((10#$PORT)) -ge 1024 && $((10#$PORT)) -le 65535 ]] || fail "端口超出范围。"
for path in "$WEB_ROOT" "$OCR_PATH" "$CONFIG_PATH" "$UNIT_DIR" "$ARTIFACT"; do
  [[ "$path" =~ ^/[a-zA-Z0-9._/-]+$ && "$path" != *'//'* && "$path" != */ ]] || fail "部署路径无效。"
  [[ "$path/" != *'/../'* && "$path/" != *'/./'* ]] || fail "路径不能包含 . 或 .. 路径段。"
done
if [[ "$MODE" == install ]]; then
  TEMP_ROOT="${TMPDIR:-/tmp}"
  TEMP_ROOT="${TEMP_ROOT%/}"
  [[ "$ARTIFACT" == *.tar.gz && ( "$ARTIFACT" == /tmp/* || "$ARTIFACT" == "$TEMP_ROOT/"* ) ]] || fail "发布包必须位于临时目录。"
  trap 'rm -f -- "$ARTIFACT"' EXIT
fi
[[ "$(id -u)" == 0 ]] || fail "OCR 部署需要 root 或免交互 sudo 权限。"
for tool in python3 systemctl tar install; do
  command -v "$tool" >/dev/null 2>&1 || fail "服务器缺少命令：$tool"
done
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || fail "OCR 需要 Python 3.9 或更新版本。"
systemctl show-environment >/dev/null || fail "服务器的 systemd 未运行。"

# 检查真实路径，避免目录符号链接把代码或配置放入公开网站目录。
python3 - "$WEB_ROOT" "$OCR_PATH" "$CONFIG_PATH" "$UNIT_DIR" <<'PY'
from pathlib import Path
import sys
web, code, config, units = map(lambda s: Path(s).resolve(), sys.argv[1:])
def contains(parent, child):
    return child == parent or parent in child.parents
if contains(web, code) or contains(code, web) or contains(web, config) or contains(code, config):
    sys.exit('OCR 目录必须与网站目录分离，私有配置必须在两者之外。')
if len(code.parts) < 3 or len(config.parent.parts) < 3:
    sys.exit('请为 OCR 代码和配置选择专用目录。')
if any(p.is_symlink() for p in (Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))):
    sys.exit('OCR 根目录、配置文件和服务目录不能是符号链接。')
PY
if [[ -e "$OCR_PATH" && ! -f "${OCR_PATH}/.guwenzi-ocr-managed" ]]; then
  [[ -d "$OCR_PATH" && -z "$(find "$OCR_PATH" -mindepth 1 -print -quit)" ]] || fail "OCR 目标目录已有非本脚本管理的内容，请另选目录。"
fi
if [[ -e "$UNIT_PATH" || -L "$UNIT_PATH" ]]; then
  [[ ! -L "$UNIT_PATH" && -f "$UNIT_PATH" ]] || fail "拒绝覆盖符号链接或非普通服务文件。"
  IFS= read -r first_line < "$UNIT_PATH"
  [[ "$first_line" == "$MARKER" ]] || fail "同名 systemd 服务不是本脚本创建的，请更换 OCR_SERVICE_NAME。"
fi
if [[ -e "$CURRENT" || -L "$CURRENT" ]]; then
  [[ -L "$CURRENT" && -d "$CURRENT" ]] || fail "OCR current 必须是有效的版本符号链接。"
  [[ "$(readlink "$CURRENT")" == "${OCR_PATH}/releases/"* ]] || fail "current 指向非本脚本管理的版本。"
fi
if [[ -e "$CONFIG_PATH" ]]; then
  [[ -f "$CONFIG_PATH" ]] || fail "配置路径不是普通文件。"
  log "已发现私有配置，发布时保留其内容。"
else
  log "首次部署将创建关闭状态的配置模板：${CONFIG_PATH}"
fi
log "部署位置 ${OCR_PATH}；服务 ${SERVICE}；监听 127.0.0.1:${PORT}"
if [[ "$MODE" != install ]]; then
  log "检查完成，未上传、写入或重启服务。"
  exit 0
fi
[[ -f "$ARTIFACT" ]] || fail "OCR 发布包不存在。"
[[ ! -e "$RELEASE_DIR" ]] || fail "发布版本已存在。"

# 发布包只允许两份普通文件，不允许链接、额外路径或路径穿越。
python3 - "$ARTIFACT" <<'PY'
import sys, tarfile
expected = {'server/ocr_server.py', 'server/ocr-config.example.json'}
with tarfile.open(sys.argv[1], 'r:gz') as archive:
    members = archive.getmembers()
    if len(members) != len(expected) or {m.name for m in members} != expected or not all(m.isfile() for m in members):
        sys.exit('OCR 发布包内容不符合预期。')
PY
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  command -v useradd >/dev/null 2>&1 || fail "需要 useradd 创建专用服务账号。"
  nologin="$(command -v nologin || true)"
  [[ -n "$nologin" ]] || fail "缺少 nologin，无法创建受限服务账号。"
  useradd --system --user-group --no-create-home --shell "$nologin" "$SERVICE_USER"
fi
[[ "$(id -u "$SERVICE_USER")" != 0 ]] || fail "拒绝以 root 账号运行 OCR。"
SERVICE_GROUP="$(id -gn "$SERVICE_USER")"
install -d -m 0755 "$OCR_PATH" "${OCR_PATH}/releases" "$RELEASE_DIR"
: > "${OCR_PATH}/.guwenzi-ocr-managed"
tar -xzf "$ARTIFACT" -C "$RELEASE_DIR" --no-same-owner --no-same-permissions
chmod 0755 "${RELEASE_DIR}/server"
chmod 0644 "${RELEASE_DIR}/server/ocr_server.py" "${RELEASE_DIR}/server/ocr-config.example.json"
CONFIG_DIR="$(dirname "$CONFIG_PATH")"
install -d -m 0750 -o root -g "$SERVICE_GROUP" "$CONFIG_DIR"
if [[ ! -e "$CONFIG_PATH" ]]; then
  install -m 0640 -o root -g "$SERVICE_GROUP" "${RELEASE_DIR}/server/ocr-config.example.json" "$CONFIG_PATH"
fi
# 仅调整读取权限，不替换已有密钥、模型或其他配置内容。
chown "root:${SERVICE_GROUP}" "$CONFIG_PATH"
chmod 0640 "$CONFIG_PATH"
python3 - "$RELEASE_DIR" "$CONFIG_PATH" <<'PY'
import importlib.util, pathlib, sys
script = pathlib.Path(sys.argv[1]) / 'server/ocr_server.py'
try:
    spec = importlib.util.spec_from_file_location('ocr_release', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_config(sys.argv[2])
except Exception:
    sys.exit('OCR 代码或私有配置校验失败；未切换版本，配置内容不输出。')
PY

PYTHON="$(command -v python3)"
[[ "$PYTHON" =~ ^/[a-zA-Z0-9_./-]+$ ]] || fail "Python 路径包含不支持的字符。"
PREVIOUS=''
[[ ! -L "$CURRENT" ]] || PREVIOUS="$(readlink "$CURRENT")"
OLD_UNIT="${RELEASE_DIR}/previous.service"
HAD_UNIT=0
WAS_ACTIVE=0
if [[ -f "$UNIT_PATH" ]]; then cp "$UNIT_PATH" "$OLD_UNIT"; HAD_UNIT=1; fi
if systemctl is-active --quiet "$SERVICE"; then WAS_ACTIVE=1; fi
if [[ "$WAS_ACTIVE" == 0 ]] || ! grep -Eq -- "--port ${PORT}$" "$UNIT_PATH"; then
  python3 - "$PORT" <<'PY'
import socket, sys
try:
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', int(sys.argv[1])))
except OSError:
    sys.exit('OCR 端口已被占用，请设置其他 OCR_PORT；未切换版本。')
PY
fi
switch_current() {
  python3 - "$1" "$CURRENT" <<'PY'
import os, sys
source, current = sys.argv[1:]
staged = current + '.next'
if os.path.lexists(staged):
    os.unlink(staged)
os.symlink(source, staged)
os.replace(staged, current)
PY
}
rollback() {
  local code="$?"
  trap - ERR
  log "部署失败，恢复之前的 OCR 版本和服务定义。"
  if [[ -n "$PREVIOUS" ]]; then switch_current "$PREVIOUS"; else rm -f -- "$CURRENT"; fi
  if [[ "$HAD_UNIT" == 1 ]]; then
    install -m 0644 "$OLD_UNIT" "$UNIT_PATH"
    systemctl daemon-reload
    if [[ "$WAS_ACTIVE" == 1 ]]; then systemctl restart "$SERVICE"; else systemctl stop "$SERVICE"; fi
  else
    systemctl disable --now "$SERVICE" >/dev/null 2>&1 || true
    rm -f -- "$UNIT_PATH"
    systemctl daemon-reload
  fi
  exit "$code"
}
trap rollback ERR
UNIT_TEMP="${RELEASE_DIR}/new.service"
cat > "$UNIT_TEMP" <<EOF
${MARKER}
[Unit]
Description=Guwenzi OCR API
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${OCR_PATH}
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=${PYTHON} ${CURRENT}/server/ocr_server.py --config ${CONFIG_PATH} --bind 127.0.0.1 --port ${PORT}
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=full
UMask=0077

[Install]
WantedBy=multi-user.target
EOF
install -m 0644 "$UNIT_TEMP" "$UNIT_PATH"
switch_current "$RELEASE_DIR"
systemctl daemon-reload
systemctl restart "$SERVICE"
# 校验响应结构，并确认进程仍受 systemd 管理；不调用外部大模型。
python3 - "$PORT" <<'PY'
import json, sys, time
from urllib.request import urlopen
for attempt in range(10):
    try:
        with urlopen('http://127.0.0.1:' + sys.argv[1] + '/api/ocr/status', timeout=2) as response:
            data = json.load(response)
        if type(data.get('configured')) is not bool:
            raise ValueError('invalid status')
        print('[ocr] 本机健康检查通过；' + ('模型参数已配置。' if data['configured'] else '模型参数未配置，部首查字仍可使用。'))
        break
    except Exception:
        if attempt == 9:
            sys.exit('OCR 健康检查失败，正在回滚。')
        time.sleep(1)
PY
systemctl is-active --quiet "$SERVICE"
systemctl enable "$SERVICE"
trap - ERR
log "OCR 后端部署完成。Nginx 反向代理需按开发文档单独配置；修改参数后执行 systemctl restart ${SERVICE}。"
