import os
import sys
import argparse
import hashlib
import multiprocessing
import subprocess
import threading
import json
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
import utils

class ExperimentProbe(object):

    def __init__(self):
        self._check_version()
        self._setup()
        self._parse_args()

    def _check_version(self):
        if sys.version_info.major != 3:
            raise Exception('Please use python version 3 to run this script!')

    def _setup(self):
        self.env = utils.get_env()
        self.result_path = self.env.out_probe_dir
        self.result_path.mkdir(parents=True, exist_ok=True)

    def _parse_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('-d', '--debug', action='store_true')
        parser.add_argument('-t', '--type', type=str, default='all',
                choices=['PCI', 'USB', 'I2C'])
        parser.add_argument('-a', '--arch', type=str, default='x86_64',
                choices=['x86_64', 'aarch64'])
        parser.add_argument('--pt', action='store_true')
        self.args = parser.parse_args()

    def _process_check(self, result_dir, result):
        check_str = ''
        if self.args.type == 'PCI':
            check_str = 'Kernel driver in use'
            success_des_dir = self.env.out_probe_success_pci_dir
            fail_des_dir = self.env.out_probe_fail_pci_dir
        elif self.args.type == 'USB':
            check_str = 'bind'
            success_des_dir = self.env.out_probe_success_usb_dir
            fail_des_dir = self.env.out_probe_fail_usb_dir
        elif self.args.type == 'I2C':
            check_str = 'UU'
            success_des_dir = self.env.out_probe_success_i2c_dir
            fail_des_dir = self.env.out_probe_fail_i2c_dir
        else:
            print('Wrong type!')
            return
        if result == -1 or check_str in result.stdout.decode():
            cmd = f'mv {result_dir} {str(success_des_dir)}'
        else:
            cmd = f'mv {result_dir} {str(fail_des_dir)}'
        subprocess.run(cmd, shell=True)

    def _docker_clean(self, name):
        cmd = f'docker stop {name}'
        subprocess.run(cmd, shell=True)
        cmd = f'docker rm {name}'
        subprocess.run(cmd, shell=True)

    def _collect_coverage(self, device, value, result_dir):
        error_site_cnt = value['ErrorSiteCnt']
        driver_name = value['Driver Name']
        ssh_cmd = f'ssh -p 12345 -i {str(self.env.out_build_sshkey).replace(str(Path.home()), "/root")} '\
            '-o "StrictHostKeyChecking no" root@localhost '
        result = self._run_ssh(device, ssh_cmd + 'date')
        returncode = result.returncode if result != -1 else -1
        fault_cnt = 0
        while returncode and fault_cnt < 20:
            fault_cnt += 1
            result = self._run_ssh(device, ssh_cmd + 'date')
            returncode = result.returncode if result != -1 else -1
        if fault_cnt == 20:
            print(f"Boot with module {device} failed!", flush=True)
            cmd = f'mv {result_dir} {self.env.out_probe_crash_dir}'
            subprocess.run(cmd, shell=True)
            self._docker_clean(device)
            return
        
        probe_cmd = self._get_perf_cmd(f"modprobe {driver_name}")
        module_cmd = (f"'cat /proc/modules | grep {driver_name.replace('-','_')} "
                "> /mnt/module.txt'")
        tree_cmd = f"'tree /dev > /mnt/dev.txt'"
        check_cmd = ""
        if self.args.type == 'PCI':
            check_cmd = f"'lspci -k -s 00:05.0'"
        elif self.args.type == 'USB':
            check_cmd = f"'ls /sys/bus/usb/devices/1-1:1.0/driver'"
        elif self.args.type == 'I2C':
            check_cmd = f"'i2cdetect -y -a 0 0x10 0x10'"
        remove_cmd = self._get_perf_cmd(f"modprobe -r {driver_name}")
        self._run_ssh(device, ssh_cmd)
        if self.args.type == 'I2C':
            if self.args.arch == 'aarch64':
                probe_versatile_cmd = f"'modprobe i2c-versatile'"
                self._run_ssh(device, ssh_cmd + probe_versatile_cmd)
            i2c_register_cmd = f"'echo {device} 0x10 > /sys/class/i2c-adapter/i2c-0/new_device'"
            self._run_ssh(device, ssh_cmd + i2c_register_cmd)
        self._run_ssh(device, ssh_cmd + f"'echo {driver_name} > /mnt/module_name.txt'")
        self._run_ssh(device, ssh_cmd + probe_cmd)
        self._run_ssh(device, ssh_cmd + module_cmd)
        self._run_ssh(device, ssh_cmd + tree_cmd)
        check_result = self._run_ssh(device, ssh_cmd + check_cmd)
        self._run_ssh(device, ssh_cmd + remove_cmd)
        for i in range(error_site_cnt):
            probe_cmd = self._get_perf_cmd(f"modprobe {driver_name} error_cnt={i}")
            remove_cmd = f"'modprobe -r {driver_name}'"
            self._run_ssh(device, ssh_cmd + probe_cmd)
            result = self._run_ssh(device, ssh_cmd + remove_cmd)
            if result == -1:
                break
        self._process_check(result_dir, check_result)
        self._docker_clean(device)

    def _get_perf_cmd(self, command):
        if self.args.pt:
            output_file = f'/mnt/perf_{hashlib.md5(command.encode()).hexdigest()}.data'
            perf_cmd = (f"perf record -o {output_file} -e intel_pt/tsc=0/k "
                    "--filter \"filter __sanitizer_cov_trace_pc\" -- ")
            perf_cmd += command
            perf_cmd += (f" && perf script -f -i {output_file} "
                    f"> {output_file.replace('data','txt')}")
            return f"'{perf_cmd}'"
        else:
            return f"'{command}'"

    def _run_ssh(self, device, command):
        cmd = f'docker exec {device} {command}'
        timeout = 5 if 'perf' in command else 3
        if self.args.debug:
            print(cmd)
        try:
            ssh = subprocess.run(cmd, shell=True, timeout=timeout, capture_output=True)
            if ssh.returncode:
                print(f"{cmd} failed!", flush=True)
            return ssh
        except subprocess.TimeoutExpired:
            print(f"{cmd} timeout!", flush=True)
            return -1

    def _start_timer(self, device, value, result_dir):
        if 'net' in device or 'scsi' in device:
            timeout = 60
        elif self.args.arch == 'aarch64':
            timeout = 40
        else:
            timeout = 30
        timer = threading.Timer(timeout, self._collect_coverage, (device, value, result_dir ))
        timer.start()

    def _process_one(self, device_name, value):
        print(f"[*]Processing module {device_name}", flush=True)
        relative_path = value['Source File'].replace(str(self.env.linux_dir) + '/', '').replace('/', '@')
        result_dir = self.result_path / relative_path
        result_dir.mkdir(parents=True, exist_ok=True)
        self._start_timer(device_name, value, result_dir)
        result_dir = Path(str(result_dir).replace(str(Path.home()), '/root'))
        result_file = result_dir / (device_name + '.txt')
        container_name = device_name
        if self.args.type == 'I2C':
            device_name += ',address=0x10'    
        if self.args.type == 'PCI' and value['PCI Func'] != 0:
            device_name += (f",multifunction=on,addr=0x6.0x0 "
                    f"-device {device_name},multifunction=on,addr=0x6.0x{value['PCI Func']}")
        cmd = ['docker', 'run', '--name', f'{container_name}', '--privileged',
                '-v', f'{self.env.project_dir}:/root/{self.env.project_name}',
                f'{str(self.env.project_name).lower()}', 'python3',
                f'/root/{self.env.project_name}/scripts/python/qemu.py', 
                '-p', '12345', '-o', f'{result_file}', f'-e={device_name}', 
                '-s', f'{result_dir}', '-f']
        if self.args.arch == 'aarch64':
            cmd.extend('-a aarch64'.split(' '))
        else:
            cmd.extend('-m fault'.split(' '))
        if self.args.pt:
            cmd.append('--host-cpu')
        subprocess.run(cmd)

    def process(self):
        print('Start to do experiment on probe function...')

        cpu_count = os.cpu_count()
        if not cpu_count:
            cpu_count = 2
        if self.args.arch == 'aarch64':
            cpu_count = cpu_count / 2
        else:
            cpu_count = cpu_count / 2
        pool_cnt = int(cpu_count)
        pool = multiprocessing.Pool(pool_cnt)
        with open(self.env.out_json_fake_devices, 'r') as f:
            file_content = json.loads(f.read())
            for key, value in file_content[self.args.type].items():
                if 'QEMU Devices' in value.keys():
                    key = value['QEMU Devices'][0]
                if value['Config Status'] != 'm' and value['Config Status'] != 'y':
                    continue
                if self.args.debug:
                    self._process_one(key, value)
                    break
                else:
                    pool.apply_async(self._process_one, (key, value, ))
        pool.close()
        pool.join()

        print('Do experiment on probe function done.')

if __name__ == '__main__':
    experiment_probe = ExperimentProbe()   
    experiment_probe.process()
