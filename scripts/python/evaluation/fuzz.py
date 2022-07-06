import re
import os
import sys
import json
import types
import argparse
import subprocess
import multiprocessing
import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
import utils

class Experiment(object):

    def __init__(self):
        self._check_version()
        self._parse_args()
        self._setup()

    def _check_version(self):
        if sys.version_info.major != 3:
            raise Exception('Please use python version 3 to run this script!')

    def _parse_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('-i', '--interrupt', action='store_true',
                help='Use this option to enable interrupt syscall')
        parser.add_argument('-s', '--syscall', action='store_true',
                help='Use this option to enable syscall')
        parser.add_argument('-t', '--test', action='store_true',
                help='Use this option to add "test" to the output dir')
        parser.add_argument('-d', '--debug', action='store_true',
                help='Use this option to debug the setting of experiment')
        parser.add_argument('-f', '--fake', action='store_true',
                help='Use this option to enable fake devices')
        self.args = parser.parse_args()

    def _setup(self):
        self.env = utils.get_env()
        self.final_json_file = self.env.out_json_dir / 'final.json'
        self.qemu_json_file = self.env.qemu_device_json
        self.out_dir_name = datetime.datetime.now().strftime("%m%d%H%M")
        self.debug_flag = False
        if self.args.interrupt:
            self.out_dir_name += '+interrupt'
        if self.args.syscall:
            self.out_dir_name += '+syscall'
        if self.args.fake:
            self.out_dir_name += '+fake'
        if self.args.test:
            self.out_dir_name += '+test'
        self.out_dir = self.env.out_experiment_dir / self.out_dir_name
        self.out_dir.mkdir(parents=True, exist_ok=True)
        cmd = f'cp {self.env.linux_build_fuzz_dir}/vmlinux {self.out_dir}'
        subprocess.run(cmd, shell=True)

    def _extract_syscall_name(self, syscall):
        pattern = re.compile(r'(.*)\(')
        result = pattern.search(syscall)
        return result.group(1)

    def _get_syscalls(self, driver):
        syscall_list = []
        if self.args.syscall:
            with open(self.env.config_syzkaller_enable_syscalls, 'r') as f:
                enable_syscall = json.loads(f.read())
                for value in enable_syscall.values():
                    flag = False
                    for subsystem in value['drivers']:
                        if subsystem in driver.stem:
                            flag = True
                            break
                    if not flag:
                        continue
                    syscall_list.extend(value['syscalls'])
        if self.args.interrupt:
            device_name = driver.stem
            template_dir = self.env.syzkaller_dir / 'sys/linux'
            if 'drivers' in device_name or 'sound' in device_name:
                template_path = template_dir / f'new_fake_{device_name}.txt'
            else:
                template_path = template_dir / f'new_qemu_{device_name}.txt'
            if template_path.exists():
                with open(template_path, 'r') as f:
                    syscall_list.append(self._extract_syscall_name(f.read().strip()))
        return syscall_list

    def _process_one(self, driver, base=False):
        syscall_list = self._get_syscalls(driver)
        if len(syscall_list) == 0:
            return

        args = types.SimpleNamespace()
        args.device = driver.stem if base == False else driver
        args.syscall_list = syscall_list
        args.out_dir = self.out_dir
        args.debug = self.args.debug
        args.base = base

        print(f'[+]Fuzzing {driver}...')
        gen_syz_template = utils.GenSyzTemplate(args)
        gen_syz_template.process()
        print(f'[+]Fuzzing {driver} done!')
        self.debug_flag = True

    def process(self):
        multiprocess_pool = multiprocessing.Pool(os.cpu_count())
        if not self.args.debug and self.args.syscall:
            components = [Path('tty'), Path('gpu'), Path('sound'), 
                    Path('video'), Path('i2c'), Path('ptp')]
            for component in components:
                multiprocess_pool.apply_async(self._process_one, (component, True, ))
        for driver_dir in self.env.out_probe_success_pci_dir.iterdir():
            for driver in driver_dir.iterdir():
                if 'dev.txt' in str(driver):
                    continue
                if not self.args.fake and ('drivers' in str(driver.stem) or 
                        'sound' in str(driver.stem) or 'arch' in str(driver.stem)):
                    continue
                if self.args.debug:
                    self._process_one(driver, )
                else:
                    multiprocess_pool.apply_async(self._process_one, (driver, ))
            if self.debug_flag:
                break
        multiprocess_pool.close()
        multiprocess_pool.join()


if __name__ == '__main__':
    experiment = Experiment()
    experiment.process()
