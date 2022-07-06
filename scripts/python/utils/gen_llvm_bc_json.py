import os
import json


class GenerateLLVMBcJson(object):

    def __init__(self, args):
        self._setup(args)
        self._check()

    def _setup(self, args):
        self.args = args
        self.llvm_bc_dir = args.llvm_bc_dir
        self.llvm_bc_json = args.llvm_bc_json
        self.linux_out = args.linux_out
        self.linux_src = args.linux_src

    def _check(self):
        if not self.llvm_bc_dir:
            raise Exception('Please input llvm_bc_dir')
        if not self.llvm_bc_json:
            raise Exception('Please input llvm_bc_json')
        if not self.linux_out:
            raise Exception('Please input linux_out')
        if not self.linux_src:
            raise Exception('Please input linux_src')

    def process(self):
        file_list = {}
        for root, _, files in os.walk(self.llvm_bc_dir):
            for file in files:
                if '.bc' == file[-3:] and '.mod' not in file:
                    file_path = os.path.join(root, file)
                    file_list[file_path] = {}
                    file_list[file_path]['Module Name'] = file[:-3]
        for root, _, files in os.walk(self.llvm_bc_dir):
            for file in files:
                if file[-4:] != '.dep':
                    continue
                dependencies = []
                dependencies_sources = []
                target_file = ''
                with open(os.path.join(root, file), 'r') as f:
                    split_content = f.read().split(':')
                    bcs = split_content[1].split(' ')
                    target_file = split_content[0]
                    for bc in bcs:
                        if bc[-3:] != '.bc':
                            continue
                        full_path = os.path.join(self.linux_out, bc)
                        dependencies.append(os.path.join(self.linux_out, bc))
                        dependencies_sources.append(os.path.join(self.linux_src, bc) \
                                .replace('.bc', '.c'))
                        file_list.pop(full_path, None)
                dep_file_path = os.path.join(root, file)
                file_list[dep_file_path[:-4]]["Dependencies"] = dependencies
                file_list[dep_file_path[:-4]]["Dependencies Sources"] = dependencies_sources
                file_list[dep_file_path[:-4]]["Source File"] = \
                    os.path.join(self.linux_src, target_file) \
                    .replace('.bc', '.c')
        json_file_list = json.dumps(file_list)

        self.llvm_bc_json.parent.mkdir(parents=True, exist_ok=True)
        with open(self.llvm_bc_json, 'w') as f:
            f.write(json_file_list)
