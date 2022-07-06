from pathlib import Path
import types


def get_env():
    env = types.SimpleNamespace()
    env.home_dir = Path.home()
    env.project_name = 'PrIntFuzz'
    env.project_dir = env.home_dir / env.project_name
    env.bin_dir = env.project_dir / 'bin'
    env.bin_aarch64_toolchain_dir = env.bin_dir / 'gcc-linaro-7.5.0-2019.12-x86_64_aarch64-linux-gnu'
    env.llvm_install_dir = env.bin_dir / 'llvm'
    env.llvm_bin_dir = env.llvm_install_dir / 'bin'
    env.static_analyzer_install_dir = env.bin_dir / 'static_analyzer'
    env.build_dir = env.project_dir / 'build'
    env.config_dir = env.project_dir / 'config'
    env.config_buildroot_dir = env.config_dir / 'buildroot'
    env.config_buildroot_config = env.config_buildroot_dir / 'config'
    env.scripts_dir = env.project_dir / 'scripts'
    env.static_analyzer_dir = env.project_dir / 'static_analyzer'
    env.third_party_dir = env.project_dir / 'third_party'
    env.third_party_linux_host_dir = env.third_party_dir / 'linux-host'
    env.scripts_shell_dir = env.scripts_dir / 'shell'
    env.scripts_python_dir = env.scripts_dir / 'python'
    env.scripts_python_utils_dir = env.scripts_python_dir / 'utils'
    env.clang_wrapper = env.scripts_shell_dir / 'clang.sh'
    env.ar_wrapper = env.scripts_shell_dir / 'ar.sh'
    env.ld_wrapper = env.scripts_shell_dir / 'ld.sh'
    env.objcopy_wrapper = env.scripts_shell_dir / 'objcopy.sh'
    env.llvm_dir = env.third_party_dir / 'llvm'
    env.llvm_build_dir = env.build_dir / 'llvm'
    env.static_analyzer_bin_dir = env.static_analyzer_install_dir / 'bin'
    env.static_analyzer_lib_dir = env.static_analyzer_install_dir / 'lib'
    env.static_analyzer_build_dir = env.build_dir / 'static_analyzer'
    env.linux_dir = env.third_party_dir / 'linux'
    env.linux_config_tool = env.linux_dir / 'scripts/config'
    env.linux_build_dir = env.build_dir / 'linux'
    env.linux_build_all_dir = env.linux_build_dir / 'linux_allmodconfig'
    env.linux_build_fuzz_dir = env.linux_build_dir / 'linux_fuzz'
    env.build_linux_fault_dir = env.linux_build_dir / 'linux_fault'
    env.build_linux_host_dir = env.linux_build_dir / 'linux_host'
    env.build_linux_aarch64_dir = env.linux_build_dir / 'linux_arm64'
    env.qemu_dir = env.third_party_dir / 'qemu'
    env.qemu_install_dir = env.bin_dir / 'qemu'
    env.qemu_bin_dir = env.qemu_install_dir / 'bin'
    env.build_qemu_dir = env.build_dir / 'qemu'
    env.third_party_gcc_dir = env.third_party_dir / 'gcc'
    env.build_gcc_dir = env.build_dir / 'gcc'
    env.install_gcc_dir = env.bin_dir / 'gcc'
    env.bin_gcc_dir = env.install_gcc_dir / 'bin'

    env.out_dir = env.project_dir / 'out'
    env.out_buildroot_dir = env.out_dir / 'buildroot-2022.02.1'
    env.out_buildroot_image = env.out_buildroot_dir / 'output/images/rootfs.ext3'
    env.out_json_dir = env.out_dir / 'json'
    env.out_json_final = env.out_json_dir / 'final.json'
    env.out_json_fake_devices = env.out_json_dir / 'fake_devices.json'
    env.out_json_config = env.out_json_dir / 'config.json'
    env.out_json_error_site = env.out_json_dir / 'error_site.json'
    env.out_json_probe_cover = env.out_json_dir / 'probe_cover.json'
    env.out_syzkaller_dir = env.out_dir / 'syzkaller'
    env.out_syzkaller_template_dir = env.out_syzkaller_dir / 'templates'
    env.out_syzkaller_config_dir = env.out_syzkaller_dir / 'configs'
    env.out_syzkaller_workdir_dir = env.out_syzkaller_dir / 'workdirs'
    env.out_build_dir = env.out_dir / 'build'
    env.out_build_rootfs = env.out_build_dir / 'rootfs'
    env.out_build_image_with_module = env.out_build_dir / 'stretch_with_module.img'
    env.out_build_image_without_module = env.out_build_dir / 'stretch_without_module.img'
    env.out_build_image_fault_injection = env.out_build_dir / 'stretch_fault_injection.img'
    env.out_build_image_nvme = env.out_build_dir / 'nvme.img'
    env.out_build_sshkey = env.out_build_dir / 'stretch.id_rsa'
    env.out_experiment_dir = env.out_dir / 'evaluation'
    env.out_probe_dir = env.out_dir / 'probe'
    env.out_probe_success_dir = env.out_probe_dir / 'success'
    env.out_probe_success_pci_dir = env.out_probe_success_dir / 'pci'
    env.out_probe_success_usb_dir = env.out_probe_success_dir / 'usb'
    env.out_probe_success_i2c_dir = env.out_probe_success_dir / 'i2c'
    env.out_probe_fail_dir = env.out_probe_dir / 'fail'
    env.out_probe_fail_pci_dir = env.out_probe_fail_dir / 'pci'
    env.out_probe_fail_usb_dir = env.out_probe_fail_dir / 'usb'
    env.out_probe_fail_i2c_dir = env.out_probe_fail_dir / 'i2c'
    env.out_probe_crash_dir = env.out_probe_dir / 'crash'
    env.out_share_dir = env.out_dir / 'share'
    env.out_linux_config_dir = env.out_dir / 'linux_config'

    env.syzkaller_dir = env.third_party_dir / 'syzkaller'
    env.go_dir = env.third_party_dir / 'go'

    env.linux_config_dir = env.config_dir / 'linux'
    env.config_linux_firmware_dir = env.linux_config_dir / 'firmware'
    env.config_json = env.linux_config_dir / 'enable_config.json'
    env.qemu_config_dir = env.config_dir / 'qemu'
    env.qemu_device_json = env.qemu_config_dir / 'qemu.json'
    env.docs_config_project_json = env.config_dir / 'project.json'
    env.config_syzkaller_dir = env.config_dir / 'syzkaller'
    env.config_syzkaller_enable_syscalls = env.config_syzkaller_dir / 'enable_syscalls.json'
    env.config_syzkaller_devices = env.config_syzkaller_dir / 'devices.json'
    env.config_syzkaller_bugs = env.config_syzkaller_dir / 'bugs.json'
    env.config_docker_dir = env.config_dir / 'docker'
    env.config_docker_dockerfile = env.config_docker_dir / 'Dockerfile'
    env.tmp_error_site_dir = Path('/tmp/ErrorSite')

    env.patch_dir = env.project_dir / 'patch'
    env.build_linux_all_patch = env.patch_dir / 'build_linux_all.patch'
    env.syzkaller_patch = env.patch_dir / 'syzkaller.patch'
    env.syzkaller_patch_tar = env.patch_dir / 'syzkaller.patch.tar.gz'
    env.linux_patch = env.patch_dir / 'linux.patch'
    env.qemu_patch = env.patch_dir / 'qemu.patch'
    env.llvm_patch = env.patch_dir / 'llvm_fault_injection.patch'

    env.build_linux_host_dir.mkdir(parents=True, exist_ok=True)
    env.out_linux_config_dir.mkdir(parents=True, exist_ok=True)
    env.build_linux_fault_dir.mkdir(parents=True, exist_ok=True)
    env.out_probe_success_dir.mkdir(parents=True, exist_ok=True)
    env.out_probe_fail_dir.mkdir(parents=True, exist_ok=True)
    env.out_probe_crash_dir.mkdir(parents=True, exist_ok=True)
    env.out_probe_success_pci_dir.mkdir(parents=True, exist_ok=True)
    env.out_probe_success_usb_dir.mkdir(parents=True, exist_ok=True)
    env.out_probe_success_i2c_dir.mkdir(parents=True, exist_ok=True)
    env.out_probe_fail_pci_dir.mkdir(parents=True, exist_ok=True)
    env.out_probe_fail_usb_dir.mkdir(parents=True, exist_ok=True)
    env.out_probe_fail_i2c_dir.mkdir(parents=True, exist_ok=True)
    env.out_share_dir.mkdir(parents=True, exist_ok=True)
    env.build_qemu_dir.mkdir(parents=True, exist_ok=True)
    env.build_gcc_dir.mkdir(parents=True, exist_ok=True)
    env.tmp_error_site_dir.mkdir(parents=True, exist_ok=True)

    return env
