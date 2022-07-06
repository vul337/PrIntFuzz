import git
import json
import socket

import utils


class GenSyzConfig(object):

    def __init__(self):
        self._setup()

    def _setup(self):
        self.env = utils.get_env()
        self.env.out_syzkaller_config_dir.mkdir(parents=True, exist_ok=True)
        self.env.out_syzkaller_workdir_dir.mkdir(parents=True, exist_ok=True)
        self.type_list = ['all', 'sound', 'fbdev', 'tty', 'gpu', 'media']

    def _get_port(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("", 0))
        s.listen(1)
        self.http_port = s.getsockname()[1]
        s.close()
        return self.http_port

    def _get_enable_syscalls(self):
        with open(self.env.config_syzkaller_enable_syscalls, 'r') as f:
            enable_syscalls = json.loads(f.read())
            return enable_syscalls[self.type]

    def _get_devices(self):
        device_list = []
        cnt = 0
        with open(self.env.config_syzkaller_devices, 'r') as f:
            devices = json.loads(f.read())
            for device in devices[self.type]:
                cnt += 1
                device_list.append(f"-device {device},bus=pcie.1,addr={hex(cnt)}")
        return " ".join(device_list)

    def _get_linux_commit(self):
        repo = git.Repo(self.env.linux_dir)
        return repo.head.object.hexsha

    def _generate_config(self):
        self.syz_config_json = self.env.out_syzkaller_config_dir / \
                f'{self.type}_config.json'
        self.syz_work_dir = self.env.out_syzkaller_workdir_dir / \
                f'{self.type}_workdir'
        self.config = {}
        self.config['name'] = self.type
        self.config['target'] = 'linux/amd64'
        self.config['http'] = f'0.0.0.0:{self._get_port()}'
        self.config['workdir'] = str(self.syz_work_dir)
        self.config['kernel_obj'] = str(self.env.linux_build_fuzz_dir)
        self.config['kernel_src'] = str(self.env.linux_dir)
        self.config['tag'] = self._get_linux_commit()
        self.config['image'] = str(self.env.out_build_image_without_module)
        self.config['sshkey'] = str(self.env.out_build_sshkey)
        self.config['syzkaller'] = str(self.env.syzkaller_dir)
        self.config['procs'] = 4
        self.config['type'] = 'qemu'
        self.config['sandbox'] = 'none'
        self.config['reproduce'] = True
        self.config['fuzzing_vms'] = 6
        self.config['vm'] = {}
        self.config['vm']['count'] = 8
        self.config['vm']['kernel'] = str(self.env.linux_build_fuzz_dir /
                'arch/x86/boot/bzImage')
        self.config['vm']['cpu'] = 4
        self.config['vm']['mem'] = 4096
        self.config['vm']['qemu'] = f'{self.env.qemu_bin_dir}/qemu-system-x86_64'
        if self.type != 'all':
            self.config['enable_syscalls'] = self._get_enable_syscalls()
            self.config['vm']['qemu_args'] = '-M q35 --enable-kvm -device pci-bridge,id=pcie.1,bus=pcie.0,chassis_nr=1 '
            self.config['vm']['qemu_args'] += self._get_devices()

    def _write_config(self):
        with open(self.syz_config_json, 'w') as f:
            f.write(json.dumps(self.config))

    def process(self):
        for config_type in self.type_list:
            self.type = config_type
            self._generate_config()
            self._write_config()


if __name__ == '__main__':
    gen_syz_config = GenSyzConfig()
    gen_syz_config.process()
