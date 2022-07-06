#!/bin/bash

source ./common.sh

set -eux

DIR=${BUILDDIR}/rootfs
U_DIR=${BUILDDIR}/debian
RELEASE=${BUILDDIR}/stretch
RELEASE_WITH_MODULE=${BUILDDIR}/stretch_with_module
RELEASE_WITHOUT_MODULE=${BUILDDIR}/stretch_without_module
RELEASE_FAULT_INJECTION=${BUILDDIR}/stretch_fault_injection

sudo rm -rf "$DIR"
sudo cp -r "$U_DIR" "$DIR"

#Set some defaults and enable promtless ssh to the machine for root.
sudo sed -i '/^root/ { s/:x:/::/ }' "$DIR"/etc/passwd
echo 'T0:23:respawn:/sbin/getty -L ttyS0 115200 vt100' | sudo tee -a "$DIR"/etc/inittab
printf '\nauto eth0\niface eth0 inet dhcp\n' | sudo tee -a "$DIR"/etc/network/interfaces
echo '/dev/root / ext4 defaults 0 0' | sudo tee -a "$DIR/"etc/fstab
echo 'debugfs /sys/kernel/debug debugfs defaults 0 0' | sudo tee -a "$DIR/"etc/fstab
echo 'securityfs /sys/kernel/security securityfs defaults 0 0' | sudo tee -a "$DIR/"etc/fstab
echo 'configfs /sys/kernel/config/ configfs defaults 0 0' | sudo tee -a "$DIR/"etc/fstab
echo 'binfmt_misc /proc/sys/fs/binfmt_misc binfmt_misc defaults 0 0' | sudo tee -a "$DIR/"etc/fstab
echo "kernel.printk = 8 4 1 7" | sudo tee -a "$DIR/"etc/sysctl.conf
echo 'debug.exception-trace = 0' | sudo tee -a "$DIR/"etc/sysctl.conf
echo "net.core.bpf_jit_enable = 1" | sudo tee -a "$DIR/"etc/sysctl.conf
echo "net.core.bpf_jit_kallsyms = 1" | sudo tee -a "$DIR/"etc/sysctl.conf
echo "net.core.bpf_jit_harden = 0" | sudo tee -a "$DIR/"etc/sysctl.conf
echo "kernel.softlockup_all_cpu_backtrace = 1" | sudo tee -a "$DIR/"etc/sysctl.conf
echo "kernel.kptr_restrict = 0" | sudo tee -a "$DIR/"etc/sysctl.conf
echo "kernel.watchdog_thresh = 60" | sudo tee -a "$DIR/"etc/sysctl.conf
echo "net.ipv4.ping_group_range = 0 65535" | sudo tee -a "$DIR/"etc/sysctl.conf
echo -en "127.0.0.1\tlocalhost\n" | sudo tee "$DIR/"etc/hosts
echo "nameserver 8.8.8.8" | sudo tee -a "$DIR/"etc/resolve.conf
echo "syzkaller" | sudo tee "$DIR/"etc/hostname
echo "mount -t 9p -o trans=virtio,version=9p2000.L hostshare /mnt" | sudo tee -a "$DIR/"etc/profile

ssh-keygen -f $RELEASE.id_rsa -t rsa -N ''
sudo mkdir -p "$DIR/"root/.ssh/
cat $RELEASE.id_rsa.pub | sudo tee "$DIR/"root/.ssh/authorized_keys

# Build a disk image
dd if=/dev/zero of=$RELEASE.img bs=16M seek=1024 count=1
sudo mkfs.ext4 -F $RELEASE.img
sudo mkdir -p /mnt/"$DIR"
sudo mount -o loop $RELEASE.img /mnt/"$DIR"
sudo cp -a "$DIR/". /mnt/"$DIR/".
sudo umount /mnt/"$DIR"
cp ${RELEASE}.img ${RELEASE_WITH_MODULE}.img
cp ${RELEASE}.img ${RELEASE_WITHOUT_MODULE}.img
cp ${RELEASE}.img ${RELEASE_FAULT_INJECTION}.img
