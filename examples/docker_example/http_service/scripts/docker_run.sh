#!/usr/bin/env bash

IMAGENAME="tomodachi-example"
LOCAL_PORT=31337

echo "> Starting container"
echo "> Forwarding local port $LOCAL_PORT to service".
echo ""

docker run -ti -p $LOCAL_PORT:80 $IMAGENAME