#!/usr/bin/env bash

IMAGENAME="tomodachi-example"
DIR="$(cd "$(dirname "$0")" && pwd)/.."

docker build -t $IMAGENAME $DIR