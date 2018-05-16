#!/usr/bin/env bash
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
TOP_DIR="$( cd "${SCRIPT_DIR}"/.. && pwd )"
ASSET_DIR="${TOP_DIR}/assets"

set -e

cd ${TOP_DIR}
sudo pip install . -U
cp ${ASSET_DIR}/data_sync.desktop ~/Desktop/
echo "Icon=${ASSET_DIR}/data_sync.png" >> ~/Desktop/data_sync.desktop
( test -f $HOME/.bashrc && grep -q "alias ds-update" ~/.bashrc || echo "alias ds-update='${SCRIPT_DIR}/update.sh'" >> $HOME/.bashrc ) || true
( test -f $HOME/.zshrc && grep -q "alias ds-update" ~/.zshrc || echo "alias ds-update='${SCRIPT_DIR}/update.sh'" >> $HOME/.zshrc ) || true
