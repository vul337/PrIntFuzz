import sys
import socket
import argparse
import subprocess
from pathlib import Path

import utils


class QEMU:

    def __init__(self, args):
        self._init()
        self._parse_args(args)
        self._setup_args()

    def _init(self):
        self.env = utils.get_env()

    def _parse_args(self, args):
        parser = argparse.ArgumentParser()
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('-k', '--kernel', type=str)
        group.add_argument('-m', '--mode', type=str, choices=['fuzz', 'fault'])
        group.add_argument('-a', '--arch', type=str, default='x86_64',
                choices=['x86_64', 'aarch64'])
        parser.add_argument('-d', '--debug', action='store_true')
        parser.add_argument('-g', '--gdb', action='store_true')
        parser.add_argument('-f', '--fault', action='store_true')
        parser.add_argument('-p', '--port', type=int, default=self._get_port())
        parser.add_argument('-e', '--extra', type=str)
        parser.add_argument('-o', '--output', type=Path)
        parser.add_argument('-s', '--share', type=Path)
        parser.add_argument('--host-cpu', action='store_true')
        parser.add_argument('--no-snapshot', action='store_true')
        self.extend_args = parser.parse_args(args)

    def _setup_args(self):
        if self.extend_args.arch == 'aarch64':
            kernel = self.env.build_linux_aarch64_dir
            image = self.env.out_buildroot_image
        else:
            if self.extend_args.mode == 'fault':
                kernel = self.env.build_linux_fault_dir
                image = self.env.out_build_image_fault_injection
            else:
                kernel = self.env.linux_build_fuzz_dir
                image = self.env.out_build_image_without_module

        self.args = []
        if self.extend_args.gdb:
            self.args.extend('gdb --args'.split(' '))
        self.args.append(f'{self.env.qemu_bin_dir}/qemu-system-{self.extend_args.arch}')
        self.args.extend('-m 4G'.split(' '))
        self.args.extend('-smp 8'.split(' '))
        machine = 'virt' if self.extend_args.arch == 'aarch64' else 'q35'
        self.args.extend(f'-M {machine}'.split(' '))
        if self.extend_args.host_cpu:
            self.args.extend(f'-cpu host'.split(' '))
        if self.extend_args.arch == 'aarch64':
            self.args.extend(f'-cpu cortex-a57'.split(' '))
            self.args.extend(f'-append:console=ttyAMA0 root=/dev/vda oops=panic panic_on_warn=1 panic=-1 ftrace_dump_on_oops=orig_cpu debug earlyprintk=serial slub_debug=UZ'.split(':'))
        if self.extend_args.arch == 'x86_64':
            kernel_image = f'{kernel}/arch/x86/boot/bzImage'
        else:
            kernel_image = f'{kernel}/arch/arm64/boot/Image'
        self.args.extend(f'-kernel {kernel_image}'.split(' '))
        if not self.extend_args.arch == 'aarch64':
            self.args.append('-enable-kvm')
        if self.extend_args.debug:
            self.args.append('-S')
        self.args.extend('-display none'.split(' '))
        self.args.append('-no-reboot')
        self.args.extend('-name VM-QEMU'.split(' '))
        self.args.extend('-device virtio-rng-pci'.split(' '))
        self.args.extend(f'-hda {image}'.split(' '))
        if not self.extend_args.no_snapshot:
            self.args.append('-snapshot')
        share_dir = self.extend_args.share if self.extend_args.share \
                else self.env.out_share_dir
        self.args.extend(
            f'-fsdev local,id=fsdev0,path={share_dir},'
            'security_model=none'.split(' '))
        self.args.extend(
            '-device virtio-9p-pci,id=fs0,fsdev=fsdev0,mount_tag=hostshare'.split(' '))
        if not self.extend_args.arch == 'aarch64':
            self.args.extend('-device qemu-xhci'.split(' '))
        if self.extend_args.extra:
            self.args.extend(f'-device {self.extend_args.extra}'.split(' '))
        self.args.extend('-device e1000,netdev=net0'.split(' '))
        self.args.extend(
            '-netdev user,id=net0,restrict=on,'
            f'hostfwd=tcp:127.0.0.1:{self.extend_args.port}-:22'
            .split(' '))
        if not self.extend_args.fault:
            self.args.extend(
                '-monitor telnet:127.0.0.1:4444,server,nowait'.split(' '))
            self.args.extend(
                '-chardev socket,id=SOCKSYZ,server,nowait,host=localhost,'
                f'port={self._get_port()}'.split(' '))
            self.args.extend('-mon chardev=SOCKSYZ,mode=control'.split(' '))
            self.args.append('-s')
        self.args.extend('-serial mon:stdio'.split(' '))

    def _get_port(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
        s.close()
        return port

    def process(self):
        output_file = open(self.extend_args.output, 'w') if self.extend_args.output \
                else None
        subprocess.run(self.args, stdout=output_file, stderr=output_file)


if __name__ == '__main__':
    qemu = QEMU(sys.argv[1:])
    qemu.process()
