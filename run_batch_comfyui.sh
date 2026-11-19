#!/usr/bin/env bash
set -euo pipefail

# このスクリプト（またはシンボリックリンク）の実体があるディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"

# 仮想環境を有効化（スクリプトと同じディレクトリにある venv を参照）
if [ -f "${SCRIPT_DIR}/.venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "${SCRIPT_DIR}/.venv/bin/activate"
else
    echo "エラー: ${SCRIPT_DIR}/.venv/bin/activate が見つかりません。" >&2
    exit 1
fi

# ターミナルからの引数をすべてそのまま Python スクリプトに転送して実行
exec python "${SCRIPT_DIR}/run_batch_comfyui_outputs.py" "$@"
