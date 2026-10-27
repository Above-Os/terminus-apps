"""Run inside the deployed container with its Studio Python (UID 1000).

Checks both real installers using offline probe wheels, then loads the actual
causal-conv1d CUDA extension in a fresh Python process. Install causal-conv1d via
Studio training or `unsloth install-kernels causal_conv1d` before running this.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


assert os.getuid() == 1000
target = Path(os.environ['PIP_TARGET'])
assert Path(os.environ['UV_CONFIG_FILE']).is_file()
for key in ('UV_CACHE_DIR', 'PIP_CACHE_DIR', 'PIP_TARGET'):
    directory = Path(os.environ[key])
    assert os.access(directory, os.W_OK), directory
env = os.environ.copy()
env['PYTHONPATH'] = str(target) + os.pathsep + env.get('PYTHONPATH', '')


def make_wheel(directory, name):
    info = name + '-1.0.dist-info'
    files = {
        name + '.py': 'VALUE = 42\n',
        info + '/METADATA': 'Metadata-Version: 2.1\nName: ' + name + '\nVersion: 1.0\n',
        info + '/WHEEL': 'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
    }
    record = info + '/RECORD'
    files[record] = ''.join(path + ',,\n' for path in [*files, record])
    wheel = directory / (name + '-1.0-py3-none-any.whl')
    with zipfile.ZipFile(wheel, 'w') as archive:
        for path, data in files.items():
            archive.writestr(path, data)
    return wheel


with tempfile.TemporaryDirectory(prefix='dependency-regression-') as temp:
    for installer in ('uv', 'pip'):
        name = 'olares_' + installer + '_probe'
        wheel = make_wheel(Path(temp), name)
        command = (['uv', 'pip', 'install', '--python', sys.executable, '--reinstall']
                   if installer == 'uv' else
                   [sys.executable, '-m', 'pip', 'install', '--upgrade'])
        subprocess.run(command + ['--no-deps', '--no-index', str(wheel)], env=env, check=True)
        check = (f'import {name}; from pathlib import Path; '
                 f'assert {name}.VALUE == 42; '
                 f'assert Path({name}.__file__).is_relative_to({str(target)!r})')
        subprocess.run([sys.executable, '-c', check], env=env, check=True)

check = ('import torch, causal_conv1d, causal_conv1d_cuda; from pathlib import Path; '
         f'assert Path(causal_conv1d_cuda.__file__).is_relative_to({str(target)!r}); '
         'print("causal-conv1d CUDA extension loads:", causal_conv1d_cuda.__file__)')
subprocess.run([sys.executable, '-c', check], env=env, check=True)
print(json.dumps({'PASS': True, 'uid': os.getuid(), 'package_directory': str(target),
                  'installers': ['uv', 'pip'], 'causal_conv1d_cuda': 'loaded'}))
