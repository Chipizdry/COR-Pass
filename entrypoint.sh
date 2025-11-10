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

# Create Prometheus multiprocess directory
export PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc
mkdir -p $PROMETHEUS_MULTIPROC_DIR
rm -rf $PROMETHEUS_MULTIPROC_DIR/*

/usr/local/bin/gunicorn main:app \
    --workers 5 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --config gunicorn_conf.py \
    --log-level info \
    --error-logfile - \
    --access-logfile -

