import json
import subprocess
from . import environment


class EnableConfig(object):

    def __init__(self, args):
        self.__setup(args)
        self.__check()

    def __setup(self, args):
        self.config_type = args.config_type
        self.config_file = args.config_file
        self.env = environment.get_env()

    def __check(self):
        if not self.env.config_json.exists():
            raise Exception(f"The json file {self.env.config_json} doesn't "
                            "exist.")
        if not self.config_file.exists():
            raise Exception(f"The config file {self.config_file} doesn't "
                            "exist.")

    def _enable_config(self, mode, config_name, config_status=''):
        cmd = (f'{self.env.linux_config_tool} --file '
               f'{self.config_file} -{mode} {config_name} {config_status}')
        print(cmd)
        subprocess.run(cmd, shell=True)

    def _enable_config_type(self, target_config_type):
        with open(self.env.config_json, 'r') as f:
            content = json.loads(f.read())
        for config_type, config in content.items():
            if config_type != target_config_type:
                continue
            for config_name, config_status in config.items():
                if 'd' == config_status or 'e' == config_status or 'm' == config_status:
                    mode = config_status
                    self._enable_config(mode, config_name)
                elif 'CMDLINE' == config_name:
                    self._enable_config('-set-str', config_name, config_status)
                else:
                    self._enable_config('-set-val', config_name, config_status)

    def _enable_general(self):
        if self.config_type == 'fault' or self.config_type == 'module':
            self.config_type = 'fuzz'
        self._enable_config_type(self.config_type)

    def _enable_driver(self):
        if self.config_type == 'fault' or self.config_type == 'module' or self.config_type == 'arm64':
            mode = 'm'
        elif self.config_type == 'fuzz':
            mode = 'e'
        else:
            return
        with open(self.env.out_json_config, 'r') as f:
            config = json.loads(f.read())
        config_list = []
        for bus, bus_config in config.items():
            if self.config_type == 'arm64' and bus != 'I2C':
                continue
            for value in bus_config.values():
                if 'Config' not in value:
                    continue
                for dep in value['Dep']:
                    if dep in config_list:
                        continue
                    config_list.append(dep)
                    self._enable_config('e', dep)
                self._enable_config(mode, value['Config'])

    def process(self):
        self._enable_driver()
        self._enable_general()
