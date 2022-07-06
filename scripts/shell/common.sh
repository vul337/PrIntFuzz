#!/bin/bash

CURRENTDIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
HOMEDIR=$( realpath "$CURRENTDIR"/../../)
export HOMEDIR=$HOMEDIR

BUILDDIR=$HOMEDIR/out/build
export BUILDDIR=$BUILDDIR

THIRD_PARTY_DIR=$HOMEDIR/third_party
LINUX_DIR=$THIRD_PARTY_DIR/fuzzing-driver-interrupt-linux
export LINUX_DIR=$LINUX_DIR
