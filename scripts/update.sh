#!/usr/bin/env bash
DS_TRUENAS_PATH="/mnt/truenas/scratch/ds_src/data-syncer"
DS_LOCAL_PATH="$HOME/ds_src/data-syncer"

LOCAL_VER=$(pip show data-syncer | grep -Po "(?<=Version: ).*" )
REMOTE_PATH="${DS_TRUENAS_PATH}/setup.py"
REMOTE_VER=$(cat ${REMOTE_PATH} | grep -Po "(?<=version=')[^']+" )
if [ "${REMOTE_VER}" != "${LOCAL_VER}" ]; then
    echo 'update data syncer local version'
    rm -rf ${DS_LOCAL_PATH}
    mkdir -p ${DS_LOCAL_PATH}
    cp -r ${DS_TRUENAS_PATH} ${DS_LOCAL_PATH}/..
    bash ${DS_LOCAL_PATH}/scripts/install.sh
else
    echo 'No update released yet'
fi
