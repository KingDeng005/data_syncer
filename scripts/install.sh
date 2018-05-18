#!/usr/bin/env bash
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
TOP_DIR="$( cd "${SCRIPT_DIR}"/.. && pwd )"
ASSET_DIR="${TOP_DIR}/assets"

set -e

# installation
cd ${TOP_DIR}
sudo pip install . -U

# set up desktop
cp ${ASSET_DIR}/data_sync.desktop ~/Desktop/

# create dot folder for log/config
cd; test -d .data_syncer || (mkdir .data_syncer && cp ${ASSET_DIR}/config.ini $HOME/.data_syncer/ds_config.ini)

# set up quick update
echo "Icon=${ASSET_DIR}/data_sync.png" >> ~/Desktop/data_sync.desktop
( test -f $HOME/.bashrc && grep -q "alias ds-update" ~/.bashrc || echo "alias ds-update='${SCRIPT_DIR}/update.sh'" >> $HOME/.bashrc ) || true
( test -f $HOME/.zshrc && grep -q "alias ds-update" ~/.zshrc || echo "alias ds-update='${SCRIPT_DIR}/update.sh'" >> $HOME/.zshrc ) || true
