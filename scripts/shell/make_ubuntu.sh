#!/bin/bash

source ./common.sh

set -eux

mkdir -p "$BUILDDIR"
pushd "$BUILDDIR" > /dev/null

DIR=debian
PREINSTALL_PKGS=gdb,net-tools,openssh-server,curl,tar,gcc,libc6-dev,time,\
strace,sudo,cmake,make,git,vim,tmux,usbutils,tcpdump,pciutils,tree,i2c-tools,\
lsscsi
RELEASE=stretch

sudo rm -rf $DIR
sudo mkdir -p $DIR
sudo chmod 0755 $DIR
sudo debootstrap --include=$PREINSTALL_PKGS --components=main $RELEASE $DIR https://mirrors.tuna.tsinghua.edu.cn/debian-elts

popd > /dev/null
