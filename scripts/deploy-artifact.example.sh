#!/usr/bin/env bash
set -Eeuo pipefail

# 复制为 deploy-artifact.sh 后，在本地脚本里填写服务器参数。
export DEPLOY_HOST=""
export DEPLOY_PORT="22"
export DEPLOY_USER=""
export DEPLOY_PATH=""

# 可选。填写私钥文件路径，如 "$HOME/.ssh/id_ed25519"。留空使用 OpenSSH 默认配置。
export DEPLOY_SSH_KEY=""

# 可选。留空时使用网站目录旁的 .backups 目录，发布后跳过 HTTP 检查。
export BACKUP_PATH=""
export HEALTH_URL=""

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/deploy-artifact-runner.sh" "$@"
