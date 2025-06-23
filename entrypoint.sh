#!/bin/bash

/usr/local/bin/alembic upgrade head

/usr/local/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --log-config log_config.yaml
