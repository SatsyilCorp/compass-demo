#!/bin/sh
set -eu

mkdir -p /opt/ml/code
tar -xzf /opt/ml/input/data/code/source.tar.gz -C /opt/ml/code
cd /opt/ml/code
exec python train.py
