#!/bin/bash

# read secrets for SAMBA
. ./corid_env.$APP_ENV

[[ ! -d $SCAN_DIR ]] &&  mkdir $SCAN_DIR
chmod -R 0777 $SCAN_DIR
mount -t cifs "$SCAN_UNC/$SCAN_UNC_DIR" $SCAN_DIR -o rw,user=$SCAN_USER,password=$SCAN_PASSWORD

# just file with the timestamp
touch $SCAN_DIR/$(date +%Y%m%d%H%M).file

# upgrade DB
/usr/local/bin/alembic upgrade head

/usr/local/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --log-config log_config.yaml
