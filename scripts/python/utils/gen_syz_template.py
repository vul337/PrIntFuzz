import json
import socket
import subprocess
import datetime
import threading
import requests
import os

from . import environment


class GenSyzTemplate(object):

    def __init__(self, args):
        self._setup(args)

    def _setup(self, args):
        self.args = args
        self.args.syscall_list.append('syz_prepare_data')
        self.config = {}
        self.env = environment.get_env()
        self.syz_device_dir = self.args.out_dir / f'{self.args.device}'
        self.syz_config_json = self.syz_device_dir / 'syzkaller_config.json'
        self.syz_work_dir = self.syz_device_dir / 'syzkaller_workdir'
        self.syz_bench = self.syz_device_dir / f'syzkaller_{datetime.datetime.now().strftime("%m%d")}.bench'
        self.syz_manager = self.env.syzkaller_dir / 'bin/syz-manager'
        self.syz_cover = self.syz_device_dir / 'syzkaller.cover'
        self.syz_probe_cover = self.syz_device_dir / 'syzkaller_probe.cover'
        self.syz_out = str(self.syz_device_dir / 'syzkaller.out')
        self.docker_port = 10001
        self.timeout = 60 * 60

        self.syz_bench.unlink(missing_ok=True)
        self.syz_device_dir.mkdir(parents=True, exist_ok=True)
        self.syz_work_dir.mkdir(parents=True, exist_ok=True)

        # Set proxy to null to avoid connection Error
        os.environ['http_proxy'] = '' 
        os.environ['https_proxy'] = ''

    def _get_port(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
        s.close()
        return port
    
    def _generate_config(self):
        self.config['target'] = 'linux/amd64'
        self.config['http'] = f'0.0.0.0:{self.docker_port}'
        self.config['workdir'] = str(self.syz_work_dir)
        self.config['kernel_obj'] = str(self.env.linux_build_fuzz_dir)
        self.config['kernel_src'] = str(self.env.linux_dir)
        self.config['image'] = str(self.env.out_build_image_without_module)
        self.config['sshkey'] = str(self.env.out_build_sshkey)
        self.config['syzkaller'] = str(self.env.syzkaller_dir)
        self.config['procs'] = 2
        self.config['type'] = 'qemu'
        self.config['sandbox'] = 'none'
        self.config['reproduce'] = False
        self.config['enable_syscalls'] = self.args.syscall_list
        if len(self.args.syscall_list) == 2:
            self.timeout = 10 * 60
        self.config['vm'] = {}
        self.config['vm']['count'] = 1
        self.config['vm']['kernel'] = str(self.env.linux_build_fuzz_dir / 'arch/x86/boot/bzImage')
        self.config['vm']['cpu'] = 1
        self.config['vm']['mem'] = 4096
        qemu_args = '--enable-kvm '
        if not self.args.base:
            if 'nvme' in self.args.device:
                qemu_args += f'-device {self.args.device},drive=nvme_img,serial=serial '
            else:
                qemu_args += f'-device {self.args.device} '
        qemu_args += (f"-fsdev local,id=fsdev0,path={self.syz_device_dir},security_model=none "
                "-device virtio-9p-pci,id=fs0,fsdev=fsdev0,mount_tag=hostshare ")
        self.config['vm']['qemu_args'] = qemu_args
        self.config['vm']['qemu'] = f'{self.env.qemu_bin_dir}/qemu-system-x86_64'

    def _write_config(self):
        with open(self.syz_config_json, 'w') as f:
            f.write(json.dumps(self.config))

    def _extract_syzkaller_port(self, output):
        cmd = f'echo "{output}" | sed -e \'s/.*127.0.0.1:\\(.*\\)-:22.*/\\1/\''
        process = subprocess.run(cmd, shell=True, capture_output=True)
        return int(process.stdout.decode('utf-8'))

    def _extract_probe_cover(self, dmesg_log):
        probe_cover = []
        for line in dmesg_log.split('\n'):
            if 'probe_cover' not in line:
                continue
            cmd = f'echo "{line}" | sed -e \'s/.*probe_cover: \\(.*\\)/\\1/\''
            process = subprocess.run(cmd, shell=True, capture_output=True)
            probe_cover.append(process.stdout.decode('utf-8'))
        return ''.join(probe_cover)

    def _collect_coverage(self):
        coverage = requests.get(f'http://127.0.0.1:{self.port}/rawcover')
        with open(self.syz_cover, 'wb') as f:
            f.write(coverage.content)
        if (os.path.exists(str(self.syz_probe_cover) + '.tmp')):
            with open(str(self.syz_probe_cover) + ".tmp", 'r') as tmp_f:
                with open(self.syz_probe_cover, 'w') as f:
                    f.write(self._extract_probe_cover(tmp_f.read()))
        cmd = f'docker stop {self.args.device}'
        subprocess.run(cmd, shell=True)
        cmd = f'docker rm {self.args.device}'
        subprocess.run(cmd, shell=True)

    def _start_timer(self):
        if self.args.debug:
            self.timeout = 60
        timer = threading.Timer(self.timeout, self._collect_coverage)
        timer.start()

    def _run_manager(self):
        self.port = self._get_port()
        debug = '-debug' if self.args.debug else ''
        cmd = ['docker', 'run', '--name', f'{self.args.device}', '--privileged', 
                f'-p{self.port}:{self.docker_port}', '--cpus=1', '-v',
                f'{self.env.project_dir}:{self.env.project_dir}', 
                f'{str(self.env.project_name).lower()}', f'{self.syz_manager}', 
                '-config', f'{self.syz_config_json}', '-bench',
                f'{self.syz_bench}', f'{debug}']
        with open(self.syz_out, 'w') as fd_syz_out:
            self.proc = subprocess.Popen(cmd, stdout=fd_syz_out, 
                    stderr=fd_syz_out)
	
    def process(self):
        self._generate_config()
        self._write_config()
        self._start_timer()
        self._run_manager()
        self.proc.wait()
