import os
import re
import kconfiglib
import json
from pathlib import Path

from . import environment


class File2Config(object):

    def __init__(self):
        self._setup()

    def _setup(self):
        self.env = environment.get_env()
        os.environ["srctree"] = str(self.env.linux_dir)
        os.environ['SRCARCH'] = 'x86'
        os.environ['CC'] = 'gcc'
        os.environ['LD'] = 'ld'
        self.config_json = {}
        self.kconfig = kconfiglib.Kconfig(self.env.linux_dir / 'Kconfig', warn=False)
        self.config_json['PCI'] = {}
        self.config_json['I2C'] = {}
        self.config_json['USB'] = {}

    def _find_necessary_path(self):
        self.file_name = self.file_path.stem
        self.makefile_path = self.file_path.parent / "Makefile"

        if not self.makefile_path.exists():
            print("Can not find makefile!")
            return False
        return True

    def _find_config_in_makefile(self, makefile_line, depth):
        general_pattern = re.compile(r'\$\(CONFIG_(.*)\)')
        result = re.search(general_pattern, makefile_line)
        if result:
            return result.group(1)
        else:
            obj_pattern = re.compile(r'(.*)-objs')
            result = re.search(obj_pattern, makefile_line)
            if result:
                return self._find_config_name(result.group(1), depth+1)
            obj_pattern = re.compile(r'(.*)-y')
            result = re.search(obj_pattern, makefile_line)
            if result:
                return self._find_config_name(result.group(1), depth+1)

    def _find_config_name(self, file_name, depth):
        if depth > 10:
            return None
        with open(self.makefile_path, 'r', errors='ignore') as f:
            makefile_lines = f.readlines()
            last_equal_line = None
            for makefile_line in makefile_lines:
                object_name = file_name + '.o'
                if '=' in makefile_line:
                    last_equal_line = makefile_line
                if object_name not in makefile_line:
                    continue
                if not last_equal_line:
                    return None
                return self._find_config_in_makefile(last_equal_line, depth)

    def _find_deps_tuple(self, deps):
        for dep in deps:
            if isinstance(dep, int):
                self.dep_mode = dep
            elif isinstance(dep, tuple):
                self._find_deps_tuple(dep)
            elif isinstance(dep, kconfiglib.Symbol):
                if dep.name == 'y' or dep.name == 'n' or dep.name == 'm' \
                        or dep.name in self.deps or dep.orig_type == 0:
                    continue
                self.deps.append(dep.name)
                self._find_deps(dep.name)
            else:
                print("dep is not a int or a tuple.")
                # print(dep, type(dep))

    def _find_deps(self, config_name):
        for node in self.kconfig.syms[config_name].nodes:
            if isinstance(node.dep, kconfiglib.Symbol):
                if node.dep.name == 'y' or node.dep.name == 'n' \
                    or node.dep.name == 'm' or node.dep.name in self.deps \
                        or node.dep.orig_type == 0:
                    continue
                self.deps.append(node.dep.name)
            elif isinstance(node.dep, tuple):
                self._find_deps_tuple(node.dep)
            else:
                print('The dep is not symbor or tuple')
                # print(self.file_path, type(node.dep), node.dep)
                return

    def _exec_config(self, config_script, config_file, mode, config):
        cmd = f'{config_script} --file {config_file} -{mode} {config}'
        res = os.popen(cmd)
        return "".join(res.readlines()).strip()

    def process(self):
        with open(self.env.out_json_final, 'r') as f:
            json_list = json.loads(f.read())
            for value in json_list.values():
                if 'Device Bus' not in value:
                    continue
                self.file_path = Path(value["Source File"])
                driver_config = {}
                print("[*]Processing file ", self.file_path)
                error = False
                if not self._find_necessary_path():
                    driver_config['Error'] = "Makefile not found!"
                    error = True
                if not error:
                    self.config = self._find_config_name(self.file_name, 0)
                    if not self.config or re.search(r'[^0-9A-Z_]+', self.config):
                        driver_config['Error'] = 'Wrong config found!'
                        error = True
                if not error:
                    self.deps = []
                    self._find_deps(self.config)
                    driver_config['Config'] = self.config
                    driver_config['Dep'] = self.deps
                self.config_json[value['Device Bus']][str(self.file_path)] = driver_config
        with open(self.env.out_json_config, 'w') as f:
            f.write(json.dumps(self.config_json))
