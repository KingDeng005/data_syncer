#!/usr/bin/env bash
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
TOP_DIR="$( cd "${SCRIPT_DIR}"/.. && pwd)"
umask 002
rsync -r  --exclude='.git' --exclude='.swp' --exclude='.pyc' ${TOP_DIR}/ /mnt/truenas/scratch/ds_src/data-syncer --update --delete
