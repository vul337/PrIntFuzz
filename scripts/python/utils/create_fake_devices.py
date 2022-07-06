import json
import subprocess

import environment

env = environment.get_env()
qemu_dir = env.qemu_dir
qemu_hw_dir = qemu_dir / 'hw'
qemu_include_dir = qemu_dir / 'include'
device_id_list = []
device_list = {}
device_list['PCI'] = {}
device_list['USB'] = {}
device_list['I2C'] = {}
pci_makefile = []
usb_makefile = []
i2c_makefile = []

def module2device(module_name):
    repo_name = str(environment.get_env().linux_dir)
    pos = module_name.find(repo_name)
    device_name = module_name[pos + len(repo_name)+1:-2]\
            .replace('/', '_').replace('-', '_')
    return device_name

def add_reg_value(content, reg_value_list):
    reg_info = []
    cnt = 0
    for reg_value in reg_value_list:
        width = reg_value[0]
        reg_value = reg_value[1]
        if width == 2:
            reg_info.append(f's->buf[{cnt}] = {hex(reg_value)};')
            cnt += 1
        elif width == 4:
            reg_info.append(f's->buf[{cnt}] = {hex(reg_value >> 8)};')
            cnt += 1
            reg_info.append(f's->buf[{cnt}] = {hex(reg_value & 0xff)};')
            cnt += 1
        elif width == 8:
            reg_info.append(f's->buf[{cnt}] = {hex(reg_value >> 24)};')
            cnt += 1
            reg_info.append(f's->buf[{cnt}] = {hex((reg_value >> 16) & 0xff)};')
            cnt += 1
            reg_info.append(f's->buf[{cnt}] = {hex((reg_value >> 8) & 0xff)};')
            cnt += 1
            reg_info.append(f's->buf[{cnt}] = {hex(reg_value & 0xff)};')
            cnt += 1

    return content.replace('#REGVALUE', '\n\t'.join(reg_info))

def create_i2c_device(device_name, device_id, reg_value):
    base_file = qemu_hw_dir / 'misc' / 'i2c_base.c'
    with open(base_file, 'r') as f:
        base_content = f.read()

    fake_i2c_dir = qemu_hw_dir / 'fake_i2c'
    fake_i2c_dir.mkdir(parents=True, exist_ok=True)
    fake_device = fake_i2c_dir / (device_name + '.c')
    i2c_makefile.append(f'common-obj-y += {device_name}.o\n')

    fake_device_content = base_content.replace('i2cbase', device_name.lower())
    fake_device_content = fake_device_content.replace('I2CBASE', device_name.upper())
    fake_device_content = fake_device_content.replace('DEVICE_ID', device_id)
    fake_device_content = add_reg_value(fake_device_content, reg_value)
    with open(fake_device, 'w') as f:
        f.write(fake_device_content)

def create_usb_device(device_name, device_id, alternate_setting):
    wacom_path = qemu_hw_dir / 'usb/usb_base.c'
    fake_usb_path = qemu_hw_dir / 'fake_usb'
    fake_usb_path.mkdir(parents=True, exist_ok=True)
    fake_device_path = fake_usb_path / (device_name + '.c')
    with open(wacom_path, 'r') as f:
        base_content = f.read()
    usb_makefile.append(f'common-obj-y += {device_name}.o\n')

    fake_device_content = base_content.replace('usb-base', device_name.lower())
    fake_device_content = fake_device_content.replace('base', device_name.lower())
    fake_device_content = fake_device_content.replace(
        'Base', device_name.capitalize())
    fake_device_content = fake_device_content.replace(
        'BASE', device_name.upper())
    fake_device_content = edit_usb_device_id(fake_device_content, device_id)
    alternate_setting_number = int(alternate_setting)
    if (alternate_setting_number != -1):
        fake_device_content = fake_device_content.replace('BINTERNATESETTING', str(alternate_setting))
    else:
        fake_device_content = fake_device_content.replace('BINTERNATESETTING', "1")
    with open(fake_device_path, 'w') as f:
        f.write(fake_device_content)

def edit_usb_device_id(fake_device_content, device_id):
    fake_device_content = fake_device_content.replace('IDVENDOR', str(device_id[1]))
    fake_device_content = fake_device_content.replace('IDPRODUCT', str(device_id[2]))
    fake_device_content = fake_device_content.replace('BCDDEVICE', str(device_id[4]))
    fake_device_content = fake_device_content.replace('BDEVICECLASS', str(device_id[5]))
    fake_device_content = fake_device_content.replace('BDEVICESUBCLASS', str(device_id[6]))
    fake_device_content = fake_device_content.replace('BDEVICEPROTOCOL', str(device_id[7]))
    fake_device_content = fake_device_content.replace('BINTERFACECLASS', str(device_id[8]))
    fake_device_content = fake_device_content.replace('BINTERFACESUBCLASS', str(device_id[9]))
    fake_device_content = fake_device_content.replace('BINTERFACEPROTOCOL', str(device_id[10]))
    fake_device_content = fake_device_content.replace('BINTERFACENUMBER', str(device_id[11]))
    return fake_device_content

def create_pci_device(device_name, device_id, driver_info):
    pci_base_path = qemu_hw_dir / 'misc/pci_base.c'
    fake_pci_path = qemu_hw_dir / 'fake_pci'
    fake_pci_path.mkdir(parents=True, exist_ok=True)
    fake_device_path = fake_pci_path / (device_name + '.c')
    pci_base_content = ""
    with open(pci_base_path, 'r') as f:
        pci_base_content = f.read()
    pci_makefile.append(f'common-obj-y += {device_name}.o\n')

    fake_device_content = pci_base_content
    fake_device_content = edit_pci_device_id(fake_device_content, device_id)
    fake_device_content = edit_pci_device_config(fake_device_content, driver_info)
    fake_device_content = edit_pci_device_resource(fake_device_content, driver_info)
    fake_device_content = edit_pci_reg(fake_device_content, driver_info)
    fake_device_content = fake_device_content.replace('pcibase', device_name)
    fake_device_content = fake_device_content.replace('/misc/', '/fake_pci/')
    fake_device_content = fake_device_content.replace(
        'PCIBASE', device_name.upper())
    fake_device_content = fake_device_content.replace(
        'PCIBase', device_name.capitalize())
    with open(fake_device_path, 'w') as f:
        f.write(fake_device_content)

def edit_pci_device_resource(fake_device_content, driver_info):
    io_bar_list = driver_info['PCI Resource']
    for io_bar in io_bar_list:
        fake_device_content = fake_device_content.replace(
                f'{io_bar}, PCI_BASE_ADDRESS_SPACE_MEMORY',
                f'{io_bar}, PCI_BASE_ADDRESS_SPACE_IO')
        fake_device_content = fake_device_content.replace(
                f'mmio{io_bar}", 16 * MiB',
                f'mmio{io_bar}", 1 * KiB')
    return fake_device_content

def edit_pci_device_config(fake_device_content, driver_info):
    config_content = []
    pci_config_list = driver_info['PCI Config']
    for pci_config in pci_config_list:
        reg_pos = pci_config[0][0]
        reg_width = pci_config[0][1]
        if reg_pos in [0, 2, 8, 44, 46]:
            continue
        reg_value = 0
        for tmp in pci_config[1]:
            reg_value = reg_value | tmp
        if reg_width == 1:
            config_content += 'pci_set_byte'
        elif reg_width == 2:
            config_content += 'pci_set_word'
        elif reg_width == 4:
            config_content += 'pci_set_long'
        config_content += f'(&pci_conf[{reg_pos}], {reg_value});\n\t'
    return fake_device_content.replace('#PCI_CONFIG#', ''.join(config_content))

def edit_pci_reg(fake_device_content, driver_info):
    reg_info = []
    cnt = 0
    for reg_value in driver_info['PCI Reg']:
        width = reg_value[0]
        reg_value = reg_value[1]
        if width == 2:
            reg_info.append(f'pcibase->buf[{cnt}] = {hex(reg_value)};')
            cnt += 1
        elif width == 4:
            reg_info.append(f'pcibase->buf[{cnt}] = {hex(reg_value >> 8)};')
            cnt += 1
            reg_info.append(f'pcibase->buf[{cnt}] = {hex(reg_value & 0xff)};')
            cnt += 1
        elif width == 8:
            reg_info.append(f'pcibase->buf[{cnt}] = {hex(reg_value >> 24)};')
            cnt += 1
            reg_info.append(f'pcibase->buf[{cnt}] = {hex((reg_value >> 16) & 0xff)};')
            cnt += 1
            reg_info.append(f'pcibase->buf[{cnt}] = {hex((reg_value >> 8) & 0xff)};')
            cnt += 1
            reg_info.append(f'pcibase->buf[{cnt}] = {hex(reg_value & 0xff)};')
            cnt += 1
    fake_device_content = fake_device_content.replace("#PROBECNT#", str(cnt));

    return fake_device_content.replace('#REGVALUE', '\n\t'.join(reg_info))

def edit_pci_device_id(fake_device_content, device_id):
    fake_device_content = fake_device_content.replace('#VENDOR_ID#', str(device_id[0]))
    fake_device_content = fake_device_content.replace('#DEVICE_ID#', str(device_id[1]))
    fake_device_content = fake_device_content.replace('#REVISION#', "0")
    fake_device_content = fake_device_content.replace(
        '#SUBSYSTEM_VENDOR_ID#', str(device_id[2]))
    fake_device_content = fake_device_content.replace(
        '#SUBSYSTEM_ID#', str(device_id[3]))
    device_id[4] = int(device_id[4], 0)
    device_id[5] = int(device_id[5], 0)
    fake_device_class_mask = 0xffffffff if device_id[5] == -1 else device_id[5]
    class_id = 0xffffffff ^ fake_device_class_mask ^ device_id[4]
    class_id = class_id >> 8
    fake_device_content = fake_device_content.replace(
        '#CLASS_ID#', str(class_id))
    return fake_device_content

def write_result():
    with open(env.out_json_fake_devices, 'w') as f:
        f.write(json.dumps(device_list))
    fake_i2c_makefile = qemu_hw_dir / 'fake_i2c' / 'Makefile.objs'
    with open(fake_i2c_makefile, 'w') as f:
        f.write(''.join(i2c_makefile))
    fake_pci_makefile = qemu_hw_dir / 'fake_pci' / 'Makefile.objs'
    with open(fake_pci_makefile, 'w') as f:
        f.write(''.join(pci_makefile))
    fake_usb_makefile = qemu_hw_dir / 'fake_usb' / 'Makefile.objs'
    with open(fake_usb_makefile, 'w') as f:
        f.write(''.join(usb_makefile))

def check_config_status(source_file):
    with open(env.out_json_config, 'r') as f:
        content = json.loads(f.read())
        for driver in content.values():
            for key, value in driver.items():
                if key != source_file or 'Config' not in value.keys():
                    continue
                cmd = (f'{env.linux_config_tool} --file {env.build_linux_fault_dir}/.config '
                        f'-s {value["Config"]}')
                result = subprocess.run(cmd, shell=True, capture_output=True).\
                        stdout.decode().strip()
                return result

def get_error_site(module_name, dependencies):
    with open(env.out_json_error_site, 'r') as f:
        error_site_json = json.loads(f.read())
        for key, value in error_site_json.items():
            if key == module_name or (dependencies and key in dependencies):
                return int(value['ErrorSiteCnt'])
    return 0

def main():
    with open(env.out_json_final, 'r') as f:
        device_id = json.loads(f.read())

    qemu_default = ['sii902x', 'wm8750', 'lm8323', 'tmp421']
    for item in device_id.values():
        if 'PCI Device ID' not in item.keys() and \
                'USB Device ID' not in item.keys() and \
                'I2C Device ID' not in item.keys():
            continue
        if 'Driver Name' not in item.keys():
            continue
        module_name = item["Source File"]
        dependencies = None
        if 'Dependencies Sources' in item.keys():
            dependencies = item['Dependencies Sources']
        print(f'[*]Processing file {module_name}')
        device_name = module2device(module_name)
        driver_info = {}
        driver_info['Source File'] = module_name
        driver_info['Config Status'] = check_config_status(module_name)
        driver_info['ErrorSiteCnt'] = get_error_site(module_name, dependencies)
        driver_info['Driver Name'] = item['Module Name']
        flag = False
        for qemu_item in qemu_default:
            if item['Driver Name'] == qemu_item:
                flag = True
                break
        if flag:
            continue
        if item.__contains__('PCI Device ID') and item["PCI Device ID"]:
            device_id = item["PCI Device ID"]["pci_device_id001"]
            create_pci_device(device_name.lower(), device_id, item['Driver Info']['PCI'])
            driver_info['PCI Func'] = item['Driver Info']['PCI']['PCI Func']
            if 'QEMU Devices' in item.keys():
                driver_info['QEMU Devices'] = item['QEMU Devices']
            device_list['PCI'][f'{device_name.lower()}'] = driver_info
        elif item.__contains__('USB Device ID') and item["USB Device ID"]:
            device_id = item["USB Device ID"]["usb_device_id001"]
            create_usb_device(device_name.lower(), device_id, item['Driver Info']['USB']['AlternateSetting'])
            device_list['USB'][f'{device_name.lower()}'] = driver_info
        elif item.__contains__('I2C Device ID') and item['I2C Device ID']:
            if 'Driver Info' not in item:
                continue
            id_cnt = 1
            device_id = item['I2C Device ID']['i2c_device_id00' + str(id_cnt)][0]
            while device_id in device_id_list:
                id_cnt += 1;
                device_id = item['I2C Device ID']['i2c_device_id00' + str(id_cnt)][0]
            else:
                device_list['I2C'][device_id] = driver_info
                device_id_list.append(device_id)
            create_i2c_device(device_name.lower(), device_id, item['Driver Info']['I2C']['Reg Value'])
        else:
            continue

    write_result()

if __name__ == '__main__':
    main()
