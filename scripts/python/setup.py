import sys
import os
import json
import subprocess
import utils
import types
import argparse

import gen_syz_config


class Setup(object):

    def __init__(self):
        self.__check_version()
        self.__setup()
        self.__parse_args()
        self.__process_args()
        self.__define_args()

    def __check_version(self):
        if sys.version_info.major != 3:
            raise Exception('Please use python version 3 to run this script!')

    def __setup(self):
        self.env = utils.get_env()
        self.components = []

    def __parse_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--get_aarch64_toolchain', action='store_true')
        parser.add_argument('--analyze', action='store_true')
        parser.add_argument('--analyze_debug', action='store_true')
        parser.add_argument('--build_analyzer', action='store_true')
        parser.add_argument('--build_llvm', action='store_true')
        parser.add_argument('--install_module', type=str, choices=['module', 'fault', 'arm64'])
        parser.add_argument('--build_syz', action='store_true')
        parser.add_argument('--build_linux_all', action='store_true')
        parser.add_argument('--build_linux_fuzz', action='store_true')
        parser.add_argument('--build_linux_fault', action='store_true')
        parser.add_argument('--build_linux_module', action='store_true')
        parser.add_argument('--build_qemu', action='store_true')
        parser.add_argument('--create_image', action='store_true')
        parser.add_argument('--build_llvm_doc', action='store_true')
        parser.add_argument('--create_docker', action='store_true')
        parser.add_argument('--find_config', action='store_true')
        parser.add_argument('--build_linux_arm64', action='store_true')

        parser.add_argument('--clean_build', action='store_true')
        parser.add_argument('--clean_config', action='store_true')
        self.args = parser.parse_args()

    def __process_args(self):
        if self.args.analyze:
            self.components.append(self.__build_llvm)
            self.components.append(self.__build_static_analyzer)
            self.components.append(self.__generate_llvm_bc_json)
            self.components.append(self.__analyze)
        elif self.args.analyze_debug:
            self.components.append(self.__build_llvm)
            self.components.append(self.__build_static_analyzer)
            self.components.append(self.__analyze)
        elif self.args.build_analyzer:
            self.components.append(self.__build_llvm)
            self.components.append(self.__build_static_analyzer)
        elif self.args.build_llvm:
            self.components.append(self.__build_llvm)
        elif self.args.install_module:
            self.components.append([self.__install_module, self.args.install_module])
        elif self.args.build_syz:
            self.components.append(self._generate_syz_config)
            self.components.append(self.__build_syzkaller)
        elif self.args.build_linux_all:
            self.components.append(self.__build_llvm)
            self.components.append(self._build_linux_all)
        elif self.args.build_linux_fuzz:
            self.components.append(self._build_linux_fuzz)
        elif self.args.build_linux_fault:
            self.components.append(self._build_linux_fault)
        elif self.args.build_linux_module:
            self.components.append([self.__enable_config, 'module'])
            self.components.append([self.__build_linux, 'module'])
            self.components.append([self.__install_module, 'module'])
        elif self.args.build_qemu:
            self.components.append(self.__build_qemu)
        elif self.args.create_image:
            self.components.append(self.__create_image)
        elif self.args.create_docker:
            self.components.append(self.__create_docker)
        elif self.args.find_config:
            self.components.append(self.__find_config)
        elif self.args.build_linux_arm64:
            self.components.append(self._build_linux_arm64)
        else:
            self.components.append(self.__build_llvm)
            self.components.append(self._build_linux_all)
            self.components.append(self.__build_static_analyzer)
            self.components.append(self.__generate_llvm_bc_json)
            self.components.append(self.__analyze)
            self.components.append(self._generate_syz_config)
            self.components.append(self.__build_syzkaller)
            self.components.append(self.__create_image)
            self.components.append(self._build_linux_fuzz)
            self.components.append(self._build_linux_fault)
            self.components.append(self.__build_qemu)
            self.components.append(self.__create_docker)

    def __define_args(self):
        self.args.llvm_bc_dir = self.env.linux_build_all_dir
        self.args.llvm_bc_json = self.env.out_json_dir / 'llvm_bc.json'
        self.args.syz_out_dir = self.env.out_syzkaller_template_dir
        self.args.entry_point_json = self.env.out_json_dir / 'entry_point.json'
        self.args.device_name_json = self.env.out_json_dir / 'device_name.json'
        self.args.ioctl_cmd_json = self.env.out_json_dir / 'ioctl_cmd.json'
        self.args.property_json = self.env.out_json_dir / 'property.json'
        self.args.pci_id_json = self.env.out_json_dir / 'pci_id.json'
        self.args.final_json = self.env.out_json_dir / 'final.json'
        self.args.linux_out = self.env.linux_build_all_dir
        self.args.linux_src = self.env.linux_dir

    def _build_linux_all(self):
        os.chdir(self.env.linux_dir)
        self._run_cmd('git restore .')
        self._run_cmd('git checkout v5.18-rc1')
        self._run_cmd(f'git apply {self.env.build_linux_all_patch}')
        self.__enable_config('allmod')
        self.__build_linux('allmod')
        self._run_cmd('git restore .')

    def _build_linux_fuzz(self):
        os.chdir(self.env.linux_dir)
        self._run_cmd('git restore .')
        self._run_cmd('git checkout v5.18-rc1')
        self._run_cmd(f'git apply {self.env.linux_patch}')
        self.__enable_config('fuzz')
        self.__build_linux('fuzz')
        self.__install_module('fuzz')
        os.chdir(self.env.linux_dir)
        self._run_cmd('git restore .')
        self._run_cmd('git clean -f')

    def _run_cmd(self, cmd):
        print('\n[CMD]:', cmd)
        subprocess.run(cmd, shell=True, check=True)

    def __build_llvm(self):
        print('[*]Bulidint LLVM...')

        os.chdir(self.env.llvm_dir)
        self._run_cmd('git checkout llvmorg-14.0.0')
        build_llvm_doc = "on" if self.args.build_llvm_doc else "off"
        self._run_cmd('cmake -G Ninja -DCMAKE_EXPORT_COMPILE_COMMANDS=on '
                f'-DCMAKE_INSTALL_PREFIX={self.env.llvm_install_dir} '
                '-DLLVM_ENABLE_PROJECTS="clang;clang-tools-extra;lld" '
                f'-DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_DOXYGEN={build_llvm_doc} '
                f'-S llvm -B {self.env.llvm_build_dir}')
        self._run_cmd(f'cmake --build {self.env.llvm_build_dir}')
        self._run_cmd(f'cmake --install {self.env.llvm_build_dir}')
        self._run_cmd(f'ln -sf {self.env.llvm_build_dir}/compile_commands.json '
               'compile_commands.json')
        os.environ['PATH'] = f'{self.env.llvm_build_dir}/bin' \
            + os.pathsep + os.environ['PATH']

        print('[+]Build LLVM finished.\n')

    def __build_static_analyzer(self):
        print('[*]Building static analyzer...')

        os.chdir(self.env.static_analyzer_dir)
        if self.args.clean_build:
            self._run_cmd(f'rm -rf {self.env.static_analyzer_build_dir}')
        cmd = \
            (f'CC=clang CXX=clang++ cmake -G Ninja '
             f'-B {self.env.static_analyzer_build_dir} '
             f'-DCMAKE_INSTALL_PREFIX={self.env.static_analyzer_install_dir} '
             f'-DCMAKE_INSTALL_RPATH={self.env.static_analyzer_lib_dir} ')
        if self.args.analyze_debug:
            cmd += f'-DCMAKE_BUILD_TYPE=DEBUG'
        else:
            cmd += f'-DCMAKE_BUILD_TYPE=RelWithDebInfo'
        self._run_cmd(cmd)
        
        self._run_cmd(f'cmake --build {self.env.static_analyzer_build_dir} ')
        self._run_cmd(f'cmake --install {self.env.static_analyzer_build_dir}')
        self._run_cmd(f'ln -sf {self.env.static_analyzer_build_dir}/'
               'compile_commands.json compile_commands.json')

        print('[+]Build static analyzer finished.\n')

    def __analyze(self):
        print('[*]Start to analyze llvm bitcode files...')

        self.__static_analyze()
        self._match_qemu()

        print('[+]Analyze llvm bitcode files finished.')

    def _match_qemu(self):
        with open(self.env.out_json_final, 'r') as fd_final:
            final_json = json.loads(fd_final.read())
        with open(self.env.qemu_device_json, 'r') as fd_qemu:
            qemu_devices = json.loads(fd_qemu.read())
            for device, qemu_value in qemu_devices.items():
                driver = qemu_value['driver']
                if driver == 'None':
                    continue
                for final_value in final_json.values():
                    if 'Driver Name' not in final_value.keys() or \
                        final_value['Driver Name'] != driver:
                        continue
                    if 'QEMU Devices' not in final_value.keys():
                        final_value['QEMU Devices'] = []
                    final_value['QEMU Devices'].append(device)
        with open(self.env.out_json_final, 'w') as fd_final:
            fd_final.write(json.dumps(final_json))

    def __generate_llvm_bc_json(self):
        print('[*]Start to generate json file...')

        gen_llvm_bc_json = utils.GenerateLLVMBcJson(self.args)
        gen_llvm_bc_json.process()

        print('[+]Generate json file finished.')

    def __static_analyze(self):
        print('[*]Start to analyze statically')

        self._run_cmd(f'{self.env.static_analyzer_bin_dir}/main '
               f'{self.args.llvm_bc_json} {self.args.property_json} '
               f'{self.args.pci_id_json} {self.args.final_json}')

        print('[+]Analyze statically finished.')

    def _generate_syz_config(self):
        print('[*]Start to generate the configurations for syzkaller...')

        config_generator = gen_syz_config.GenSyzConfig()
        config_generator.process()

        print('[*]Generate the configurations for syzkaller finished.')

    def __find_config(self):
        print('[*]Start to find the config of driver...')

        kconfig_file = self.args.linux_src / 'init/Kconfig'
        self._run_cmd(f'sed -i "/\tmodules/d" {kconfig_file}')

        find_config = utils.File2Config()
        find_config.process()

        self._run_cmd('sed -i '
               '"s/\\(bool \\"Enable loadable module support\\"\\)/"'
               '"\\1\\n\\tmodules/" '
               f'{kconfig_file}')

        print('[+]Find the config of driver finished.')

    def __enable_config(self, mode):
        print('[*]Start to enable driver configurations...')

        arch = 'x86_64'
        if mode == 'fuzz':
            output_dir = self.env.linux_build_fuzz_dir
        elif mode == 'module':
            output_dir = self.env.linux_build_mod_dir
        elif mode == 'fault':
            output_dir = self.env.build_linux_fault_dir
        elif mode == 'allmod':
            output_dir = self.env.linux_build_all_dir
        elif mode == 'arm64':
            output_dir = self.env.build_linux_aarch64_dir
            arch = 'arm64'
        else:
            raise Exception(f"mode {mode} is wrong!")

        if self.args.clean_build:
            self._run_cmd(f'rm -r {output_dir}')
        output_dir.mkdir(parents=True, exist_ok=True)
        config_bak_path = self.env.out_linux_config_dir / f'linux_{arch}_{mode}.config'
        if config_bak_path.exists() and not self.args.clean_config and not self.args.clean_build:
            self._run_cmd(f'cp {config_bak_path} {output_dir}/.config')
        else:
            os.chdir(self.env.linux_dir)
            args = types.SimpleNamespace()

            if mode == 'allmod':
                self._run_cmd(f'make O={output_dir} CC=clang allmodconfig')
            else:
                self._run_cmd(f'make ARCH={arch} O={output_dir} defconfig')
                self._run_cmd(f'make ARCH={arch} O={output_dir} kvm_guest.config')

                if not self.env.out_json_config.exists():
                    self.__find_config()

            args.config_type = mode
            args.config_file = output_dir / '.config'
            enable_config = utils.EnableConfig(args)
            enable_config.process()
            self._run_cmd(f'cp {args.config_file} {config_bak_path}')

        print('[+]Enable driver configuations finished.')

    def __build_linux(self, mode):
        print(f'[*]Start to build linux {mode}...')

        ARCH = 'x86_64'
        CROSS_COMPILE = ''
        extra_option = ''
        if mode == 'fuzz':
            CC = "gcc"
            AR = 'ar'
            LD = 'ld'
            OBJCOPY = 'objcopy'
            output_dir = self.env.linux_build_fuzz_dir
            os.environ['BUILD_TYPE'] = 'FUZZ'
        elif mode == 'fault':
            CC = f'{self.env.clang_wrapper}'
            AR = f'{self.env.ar_wrapper}'
            LD = f'{self.env.ld_wrapper}'
            OBJCOPY = f'{self.env.objcopy_wrapper}'
            output_dir = self.env.build_linux_fault_dir
            os.environ['BUILD_TYPE'] = 'FAULT'
        elif mode == 'allmod':
            CC = f'{self.env.clang_wrapper}'
            AR = f'{self.env.ar_wrapper}'
            LD = f'{self.env.ld_wrapper}'
            OBJCOPY = f'{self.env.objcopy_wrapper}'
            output_dir = self.env.linux_build_all_dir
            os.environ['BUILD_TYPE'] = 'ALLMOD'
        elif mode == 'arm64':
            ARCH = 'arm64'
            CROSS_COMPILE = ''
            CC = f'{self.env.clang_wrapper}'
            AR = f'{self.env.ar_wrapper}'
            LD = f'{self.env.ld_wrapper}'
            OBJCOPY = f'{self.env.objcopy_wrapper}'
            output_dir = self.env.build_linux_aarch64_dir
            extra_option = 'LLVM=1'
            os.environ['ARCHIVE'] = 'llvm-ar'
            os.environ['LINKER'] = 'ld.lld'
            os.environ['COPY'] = 'llvm-objcopy'
        else:
            raise Exception("Wrong mode!")

        os.chdir(self.env.linux_dir)
        self._run_cmd(f'make ARCH={ARCH} {extra_option} O={output_dir} CROSS_COMPILE={CROSS_COMPILE} '
               f'CC={CC} AR={AR} LD={LD} OBJCOPY={OBJCOPY} olddefconfig')
        self._run_cmd(f'make ARCH={ARCH} {extra_option} O={output_dir} CROSS_COMPILE={CROSS_COMPILE} '
               f'CC={CC} AR={AR} LD={LD} OBJCOPY={OBJCOPY} -j{os.cpu_count()}')

        if mode == 'allmod':
            self._run_cmd(f'{self.env.linux_dir}/scripts/clang-tools/'
                   f'gen_compile_commands.py -d {self.env.linux_build_all_dir} '
                   f'-o {self.env.linux_dir}/compile_commands.json')

        print(f'[+]Build linux {mode} finished.')

    def __install_module(self, mode):
        print(f'[*]Start to install module to linux {mode}...')

        ARCH='x86_64'
        if mode == 'fault':
            output_dir = self.env.build_linux_fault_dir
            image = self.env.out_build_image_fault_injection
        elif mode == 'fuzz':
            output_dir = self.env.linux_build_fuzz_dir
            image = self.env.out_build_image_without_module
        elif mode == 'arm64':
            output_dir = self.env.build_linux_aarch64_dir
            image = self.env.out_buildroot_image
            ARCH = 'arm64'
        else:
            raise Exception("Wrong mode!")

        os.chdir(self.env.linux_dir)
        self._run_cmd(f'sudo rm -rf {self.env.out_build_rootfs}/lib/modules')
        self._run_cmd(f'sudo make ARCH={ARCH} O={output_dir} modules_install '
               f'INSTALL_MOD_PATH={self.env.out_build_rootfs}')
        os.chdir(self.env.out_build_dir)
        self._run_cmd(f'sudo rm -rf ./share/lib/modules')
        self._run_cmd('mkdir -p ./share && '
               f'sudo mount -o loop {image} ./share && '
               f'sudo cp -a {self.env.out_build_rootfs}/lib/modules/ ./share/lib/ && '
               'sudo umount ./share')

        print(f'[*]Install module to linux {mode} finished.')

    def __build_qemu(self):
        print('[*]Start to build qemu...')

        if self.args.clean_build:
            self._run_cmd(f'rm -r {self.env.build_qemu_dir}')
            self.env.build_qemu_dir.mkdir(parents=True, exist_ok=True)

        os.chdir(self.env.qemu_dir)
        self._run_cmd('git checkout v4.2.1')
        self._run_cmd(f'git apply {self.env.qemu_patch}')

        create_fake_device = self.env.scripts_python_utils_dir / \
            'create_fake_devices.py'
        self._run_cmd(f'python3 {create_fake_device}')

        os.chdir(self.env.qemu_dir)
        self._run_cmd('cp hw/usb/desc.h hw/fake_usb/')

        os.chdir(self.env.build_qemu_dir)
        self._run_cmd(f'{self.env.qemu_dir}/configure '
                '--target-list=x86_64-softmmu,aarch64-softmmu --enable-debug '
                f'--enable-virtfs --prefix={self.env.qemu_install_dir} '
                '--disable-xkbcommon --disable-gtk --disable-libssh')
        self._run_cmd(f'make -j{os.cpu_count()} && make install')
        self._run_cmd(f'ln -sf {self.env.build_qemu_dir}/compile_commands.json '
                f'{self.env.qemu_dir}/compile_commands.json')

        os.chdir(self.env.qemu_dir)
        self._run_cmd('git restore .')
        self._run_cmd('git clean -fd')

        print('[+]Build qemu finished.')

    def __build_syzkaller(self):
        print('[*]Start to build syzkaller...')

        if not self.env.go_dir.exists():
            self.__download_go()

        os.chdir(self.env.syzkaller_dir)
        os.environ['PATH'] = f'{self.env.third_party_dir}/go/bin' \
            + os.pathsep + os.environ['PATH']
        self._run_cmd(f'git checkout 3cd800e43')
        self._run_cmd(f'tar -xzvf {self.env.syzkaller_patch_tar} '
                f'-C {self.env.patch_dir}')
        self._run_cmd(f'git apply {self.env.syzkaller_patch}')
        self._run_cmd('make')

        print('[+]Build syzkaller finished.')

    def __download_go(self):
        print('[*]Start to download go...')

        os.chdir(self.env.third_party_dir)
        go_url = 'https://go.dev/dl/go1.17.4.linux-amd64.tar.gz'
        self._run_cmd(f'wget -c {go_url}')
        self._run_cmd('tar -xzvf go1.17.4.linux-amd64.tar.gz')
        self._run_cmd('rm go1.17.4.linux-amd64.tar.gz')

        print('[+]Download go finished.')

    def _copy_to_image(self, image):
        os.chdir(self.env.out_build_dir)
        self._run_cmd('mkdir -p ./share')
        self._run_cmd(f'sudo mount -o loop {image} ./share')
        self._run_cmd(f'sudo cp -a {self.env.config_linux_firmware_dir} '
                './share/lib/firmware')
        self._run_cmd(f'sudo cp {self.env.linux_dir}/tools/perf/perf '
                './share/usr/bin')
        self._run_cmd('sudo umount ./share')

    def _create_x86_image(self):
        if not self.args.clean_build and \
                self.env.out_build_image_with_module.exists():
            print(f'[+]{self.env.out_build_image_with_module} already exists!')
            return

        print('[*]Start to create image...')

        os.chdir(self.env.scripts_shell_dir)
        self._run_cmd('bash make_ubuntu.sh')
        self._run_cmd('bash make_rootfs.sh')

        os.chdir(self.env.linux_dir / 'tools/perf')
        self._run_cmd('make LDFLAGS=-static')

        self._copy_to_image(self.env.out_build_image_with_module)
        self._copy_to_image(self.env.out_build_image_without_module)
        self._copy_to_image(self.env.out_build_image_fault_injection)

        print('[+]Create image finished.')

    def _create_aarch64_image(self):
        if self.env.out_buildroot_image.exists():
            print(f'[+]{self.env.out_buildroot_image} already exists!')
            return

        os.chdir(self.env.out_dir)
        url = 'https://buildroot.uclibc.org/downloads/buildroot-2022.02.1.tar.gz'
        self._run_cmd(f'wget -c {url}')
        self._run_cmd(f'tar -xzvf buildroot-2022.02.1.tar.gz')
        self._run_cmd(f'cp {self.env.config_buildroot_config} '
                f'{self.env.out_buildroot_dir}/.config')
        os.chdir(self.env.out_buildroot_dir)
        self._run_cmd(f'make -j{os.cpu_count()}')

    def __create_image(self):

        self._create_x86_image()
        # self._create_aarch64_image()

    def _build_linux_arm64(self):
        print('[*]Start to build linux with fault injection...')

        os.chdir(self.env.llvm_dir)
        self._run_cmd('git checkout Fault-Injection_v14')

        self.__build_llvm()
        self.__enable_config('arm64')
        self.__build_linux('arm64')
        self.__install_module('arm64')

        os.chdir(self.env.llvm_dir)
        self._run_cmd('git checkout PrIntFuzz')

    def _collect_error_site(self):
        output_file = {}
        for file in self.env.tmp_error_site_dir.iterdir():
            if not file.is_file():
                continue
            with open(file, 'r') as f:
                lines = f.read().splitlines()
                output_file[lines[0]] = {}
                output_file[lines[0]]['ErrorSiteCnt'] = lines[1]
                output_file[lines[0]]['ErrorSite'] = lines[2:]
        with open(self.env.out_json_error_site, 'w') as f:
            f.write(json.dumps(output_file))

    def _build_linux_fault(self):
        print('[*]Start to build linux with fault injection...')

        os.chdir(self.env.llvm_dir)
        self._run_cmd('git checkout llvmorg-14.0.0')
        self._run_cmd(f'git apply {self.env.llvm_patch}')

        if self.args.clean_build:
            self._run_cmd(f'rm -rf {self.env.tmp_error_site_dir}')

        self.__build_llvm()
        os.chdir(self.env.linux_dir)
        self.__enable_config('fault')
        self.__build_linux('fault')
        self.__install_module('fault')
        self._collect_error_site()

        os.chdir(self.env.llvm_dir)
        self._run_cmd('git restore .')
        self._run_cmd('git checkout llvmorg-14.0.0')
        
        print('[+]Build linux with fault injection finished.')

    def __create_docker(self):
        print('[*]Start to create docker...')

        self._run_cmd(f'docker build -t {str(self.env.project_name).lower()} '
                f'-f {self.env.config_docker_dockerfile} {self.env.config_docker_dir}')

        print('[+]Create docker finished.')

    def _get_aarch64_toolchain(self):
        if not self.env.bin_aarch64_toolchain_dir.exists():
            os.chdir(self.env.bin_dir)
            url = 'https://releases.linaro.org/components/toolchain/binaries/latest-7/aarch64-linux-gnu/gcc-linaro-7.5.0-2019.12-x86_64_aarch64-linux-gnu.tar.xz'
            self._run_cmd(f'wget -c {url}')
            self._run_cmd('tar -xJvf gcc-linaro-7.5.0-2019.12-x86_64_aarch64-linux-gnu.tar.xz')
        os.environ['PATH'] = f'{self.env.bin_aarch64_toolchain_dir}/bin' \
            + os.pathsep + os.environ['PATH']

    def process(self):
        print('[*]Start setting up...')

        for component in self.components:
            if isinstance(component, list):
                component[0](component[1])
            else:
                component()

        print('[+]Congratulations! Setting up finished.')


if __name__ == '__main__':
    setup = Setup()
    setup.process()
