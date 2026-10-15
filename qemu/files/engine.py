"""Non-root QEMU supervisor with setup progress and guest filesystem expansion."""
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import shlex
import sys
import socket
import subprocess
import threading
import time
import vm_platform

ROOT, STORE, TMP = Path('/opt/olares'), Path('/storage'), Path('/tmp')
GIB = 1024 ** 3
stop = threading.Event()
state = {'phase': 'preparing', 'message': 'Checking virtual machine settings.',
         'message_zh': '正在检查虚拟机设置。', 'ready': False, 'connectable': False,
         'percent': None, 'warning': ''}
web = vm = transfer = None
guest_username = "ubuntu"


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value), encoding='utf-8')
    temporary.chmod(0o600)
    temporary.replace(path)


def publish(phase=None, en=None, zh=None, **values):
    state.update(values)
    if phase:
        state['phase'] = phase
    if en:
        state['message'], state['message_zh'] = en, zh or en
    state['updated'] = int(time.time())
    write_json(TMP / 'status.json', state)
    if phase:
        print(f"{phase}: {state['message']}", flush=True)


def run(argv, **kwargs):
    return subprocess.run(argv, check=True, text=True, capture_output=True, **kwargs).stdout


def integer(name, default, minimum, maximum):
    text = os.environ.get(name, str(default))
    if not re.fullmatch(r'[0-9]+', text) or not minimum <= int(text) <= maximum:
        raise ValueError(f'{name} must be {minimum}–{maximum}.')
    return int(text)


def download(entry):
    global transfer
    part, source = STORE / 'server.qcow2.part', STORE / 'download-source.json'
    previous_source = json.loads(source.read_text()) if source.exists() else {}
    if previous_source.get('url') != entry['url']:
        part.unlink(missing_ok=True)
    write_json(source, {'url': entry['url']})
    expected = entry.get('digest')
    if not expected:
        raw = run(['curl', '-4', '-fsSL', '--connect-timeout', '20', '--max-time', '120',
                   '--retry', '3', entry['sums']], timeout=500)
        name = entry['url'].rsplit('/', 1)[1]
        for line in raw.splitlines():
            fields = line.split()
            if len(fields) == 2 and fields[1].lstrip('*') == name:
                expected = fields[0]
                break
    length = 64 if entry['algorithm'] == 'sha256' else 128
    if not expected or not re.fullmatch('[0-9a-f]{' + str(length) + '}', expected):
        raise ValueError('Official checksum not found for the selected image.')
    headers = TMP / 'download.headers'
    headers.unlink(missing_ok=True)
    publish('downloading', 'Downloading the system image from CDN. Interrupted downloads resume automatically.',
            '正在从 CDN 下载系统镜像，中断后可在重启时继续下载。', downloaded=part.stat().st_size if part.exists() else 0)
    with (TMP / 'download.log').open('w') as log:
        transfer = subprocess.Popen(['curl', '-4', '-fL', '--connect-timeout', '20',
            '--max-time', '3600', '--retry', '8', '--retry-all-errors',
            '--retry-delay', '3', '--continue-at', '-',
            '--dump-header', str(headers), '-o', str(part), entry['url']],
            stdout=subprocess.DEVNULL, stderr=log)
        previous = part.stat().st_size if part.exists() else 0
        while transfer.poll() is None:
            if stop.wait(1):
                transfer.terminate()
                raise InterruptedError()
            current = part.stat().st_size if part.exists() else 0
            total = 0
            if headers.exists():
                raw = headers.read_text(errors='replace')
                ranges = re.findall(r'(?im)^content-range:.*?/(\d+)\s*$', raw)
                lengths = re.findall(r'(?im)^content-length:\s*(\d+)\s*$', raw)
                total = int(ranges[-1]) if ranges else int(lengths[-1]) if lengths else 0
            publish(downloaded=current, total=total, speed=max(0, current - previous),
                    percent=min(100, current * 100 / total) if total else None)
            previous = current
        if transfer.returncode:
            print(f'Image download failed after retries (curl exit {transfer.returncode}). See /tmp/download.log.', flush=True)
            raise RuntimeError('Image download failed. Restart the app to retry; downloaded data is retained.')
    publish('verifying', 'Verifying the image checksum.', '正在校验镜像完整性。', speed=0, percent=None)
    digest = hashlib.new(entry['algorithm'])
    with part.open('rb') as file:
        for chunk in iter(lambda: file.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        part.unlink()
        raise RuntimeError('Image checksum mismatch. The incomplete image was removed; restart to download again.')
    return part


def agent(command, arguments=None, timeout=3):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(timeout)
        connection.connect('/tmp/qga.sock')
        reader = connection.makefile('rb')
        sync_id = int(time.time() * 1000)
        requests = [{'execute': 'guest-sync-delimited', 'arguments': {'id': sync_id}},
                    {'execute': command, **({'arguments': arguments} if arguments else {})}]
        for index, payload in enumerate(requests):
            connection.sendall(json.dumps(payload).encode() + b'\n')
            while True:
                line = reader.readline()
                if not line:
                    raise RuntimeError('Guest agent disconnected.')
                try:
                    response = json.loads(line.lstrip(b'\xff'))
                except ValueError:
                    continue
                if 'error' in response:
                    raise RuntimeError(response['error'].get('desc', 'Guest agent error'))
                if 'return' in response:
                    if index == 0 and response['return'] != sync_id:
                        continue
                    break
        return response['return']


def guest_exec(script, timeout=240):
    askpass = TMP / 'ssh-askpass'
    askpass.write_text('#!' + sys.executable + '\nimport os\nprint(os.environ["VM_PASSWORD"])\n')
    askpass.chmod(0o700)
    env = dict(os.environ, SSH_ASKPASS=str(askpass), SSH_ASKPASS_REQUIRE='force', DISPLAY='olares:0')
    argv = ['ssh', '-p', '2222', '-o', 'ConnectTimeout=5', '-o', 'ConnectionAttempts=1',
            '-o', 'StrictHostKeyChecking=accept-new', '-o', 'UserKnownHostsFile=/storage/ssh_known_hosts',
            '-o', 'PreferredAuthentications=password', '-o', 'PubkeyAuthentication=no',
            '-o', 'NumberOfPasswordPrompts=1', guest_username + '@127.0.0.1',
            'sudo -n /bin/sh -c ' + shlex.quote(script)]
    try:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, env=env, text=True,
                                capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise TimeoutError('Guest maintenance timed out. Check the system console.') from None
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or 'Guest operation failed.')[-700:])
    return result.stdout


GROW_ROOT = r'''set -eu
source=$(findmnt -n -o SOURCE /)
root=$(readlink -f "${source%%\[*}")
parent=$(lsblk -n -o PKNAME "$root" | head -n 1)
partition_file="/sys/class/block/$(basename "$root")/partition"
part=''
if [ -r "$partition_file" ]; then part=$(cat "$partition_file"); fi
if [ -z "$parent" ] || [ -z "$part" ]; then
  echo 'Automatic expansion requires a root filesystem on a plain disk partition.' >&2; exit 1
fi
set +e
result=$(growpart "/dev/$parent" "$part" 2>&1); code=$?
set -e
if [ "$code" -ne 0 ]; then
  case "$result" in *NOCHANGE*) ;; *) echo "$result" >&2; exit 1;; esac
fi
case "$(findmnt -n -o FSTYPE /)" in
  ext4|ext3|ext2) resize2fs "$root" ;;
  xfs) xfs_growfs / ;;
  btrfs) btrfs filesystem resize max / ;;
  *) echo 'Filesystem requires manual expansion.' >&2; exit 1 ;;
esac
df -B1 /
'''

WAIT_INIT = '''cloud-init status --wait
code=$?
if [ "$code" -eq 2 ]; then echo OLARES_CLOUD_INIT_WARNING; exit 0; fi
exit "$code"
'''


def prepare_seed(entry):
    seed = TMP / 'seed'
    seed.mkdir(exist_ok=True)
    packages = ['qemu-guest-agent', 'cloud-guest-utils' if entry['group'] == 'sudo' else 'cloud-utils-growpart']
    config = {'users': [{'name': entry['user'], 'groups': [entry['group']], 'shell': '/bin/bash',
                'sudo': 'ALL=(ALL) NOPASSWD:ALL', 'lock_passwd': False,
                'plain_text_passwd': os.environ['VM_PASSWORD']}],
              'ssh_pwauth': True, 'chpasswd': {'expire': False},
              'apt': {'conf': 'Acquire::Retries "3";\nAcquire::IndexTargets::deb::CNF::DefaultEnabled "false";\n'},
              'packages': packages, 'runcmd': [['systemctl', 'start', 'qemu-guest-agent']]}
    if entry['user'] == 'fedora':
        config['preserve_hostname'] = True
    (seed / 'user-data').write_text('#cloud-config\n' + json.dumps(config))
    (seed / 'meta-data').write_text('instance-id: olares-qemu-server-v1\nlocal-hostname: linux-server\n')
    run(['genisoimage', '-quiet', '-output', '/tmp/seed.iso', '-volid', 'cidata',
         '-joliet', '-rock', str(seed / 'user-data'), str(seed / 'meta-data')])
    write_json(TMP / 'connection.json', {'username': entry['user'], 'password': os.environ['VM_PASSWORD']})


def configure_and_start():
    global vm, guest_username
    cpu = integer('CPU_CORES', 2, 1, 8)
    memory = integer('MEMORY_GB', 2, 1, 32)
    disk = integer('DISK_SIZE_GB', 32, 16, 512)
    distribution = os.environ.get('DISTRIBUTION', 'ubuntu2404')
    arch = vm_platform.architecture()
    catalog_file = 'catalog-arm64.json' if arch == 'arm64' else 'catalog.json'
    catalog = json.loads((ROOT / catalog_file).read_text())
    if distribution not in catalog:
        raise ValueError('Unsupported distribution/version selection.')
    entry = dict(catalog[distribution])
    guest_username = entry['user']
    cdn = os.environ.get('CDN_HOST', 'https://cdn.olares.com').rstrip('/')
    for field in ('url', 'sums'):
        if field in entry:
            entry[field] = cdn + '/linux/' + entry[field].rsplit('/', 1)[-1]
    publish(title=entry['title'], cpu=cpu, memory=memory, disk=disk, architecture=arch)
    fd = os.open('/dev/kvm', os.O_RDWR)
    try:
        if fcntl.ioctl(fd, 0xAE00, 0) != 12:
            raise RuntimeError('Unsupported KVM API.')
    finally:
        os.close(fd)
    image, marker = STORE / 'server.qcow2', STORE / 'distribution'
    arch_marker = STORE / 'architecture'
    vm_platform.check_disk_architecture(arch, image, arch_marker)
    if image.exists() and not marker.exists():
        marker.write_text('ubuntu2404\n')
    if marker.exists() and marker.read_text().strip() != distribution:
        raise RuntimeError('The selected version does not match the existing disk. Restore the original selection or create a new disk.')
    if not image.exists():
        if not 8 <= len(os.environ.get('VM_PASSWORD', '')) <= 128:
            raise ValueError('Set an initial password of 8–128 characters when installing a new VM.')
        part = download(entry)
        publish('disk', 'Creating the persistent system disk.', '正在创建持久化系统盘。', percent=None)
        original = json.loads(run(['qemu-img', 'info', '--output=json', str(part)]))['virtual-size']
        if disk * GIB < original:
            raise ValueError('Selected disk size is smaller than the official image minimum.')
        run(['qemu-img', 'resize', str(part), str(disk * GIB)])
        marker.write_text(distribution + '\n')
        arch_marker.write_text(arch + chr(10))
        part.replace(image)
    current = json.loads(run(['qemu-img', 'info', '--output=json', str(image)]))['virtual-size']
    if disk * GIB > current:
        publish('disk', 'Saving a disk backup before expansion.', '正在保存扩容前的磁盘备份。', percent=None)
        backup = STORE / 'before-expansion.qcow2.tmp'
        run(['qemu-img', 'convert', '-O', 'qcow2', str(image), str(backup)])
        backup.replace(STORE / 'before-expansion.qcow2')
        if stop.is_set():
            raise InterruptedError()
        publish('disk', 'Expanding the virtual disk. Existing data is retained.', '正在扩大虚拟磁盘，保留已有数据。', percent=None)
        run(['qemu-img', 'resize', str(image), str(disk * GIB)])
        current = disk * GIB
    elif disk * GIB < current:
        publish(warning=f'Disk shrink is not supported. The existing {current // GIB} GiB disk is retained. Set DISK_SIZE_GB to {current // GIB} or larger.')
    publish(disk=current // GIB)
    vm_platform.prepare_firmware(arch, STORE)
    prepare_seed(entry)
    publish('booting', 'Starting the virtual machine with KVM acceleration.', '正在使用 KVM 加速启动虚拟机。', percent=None)
    vm = subprocess.Popen(vm_platform.command(arch, cpu, memory, image, STORE))
    publish('initializing', 'Waiting for SSH and cloud-init. The console is available during setup.',
            '正在等待 SSH 和系统初始化，期间可以打开控制台。', connectable=True)
    end = time.monotonic() + 900
    while time.monotonic() < end and not stop.wait(3):
        if vm.poll() is not None:
            raise RuntimeError('The virtual machine stopped during startup. Check container logs and the console.')
        try:
            guest_exec('true', timeout=15)
            break
        except (OSError, RuntimeError, ValueError, TimeoutError):
            pass
    else:
        raise TimeoutError('SSH is not ready. Open the console and check the login service; the virtual disk is retained.')
    init_output = guest_exec(WAIT_INIT, timeout=600)
    if 'OLARES_CLOUD_INIT_WARNING' in init_output:
        publish(warning='Cloud-init completed with recoverable warnings. Run cloud-init status --long for details.')
    publish('expanding', 'Checking the root partition and filesystem capacity.', '正在检查并扩展系统分区与文件系统。')
    try:
        output = guest_exec(GROW_ROOT)
        print('Guest filesystem check:\n' + output, flush=True)
    except (RuntimeError, TimeoutError) as error:
        publish(warning=state.get('warning', '') + '\nAutomatic filesystem expansion needs attention: ' + str(error))
    publish('ready', 'The server is ready. CPU and memory edits restart the VM; disk size can only grow.',
            '服务器已就绪。修改 CPU 和内存后会重启，磁盘仅支持扩容。', ready=True, percent=100)
    while not stop.wait(2):
        if vm.poll() is not None:
            publish('stopped', 'The guest has shut down. Restart the app to start it again.', '虚拟机已关机，重启应用可再次启动。', ready=False)
            stop.wait()
            break


def shutdown():
    if transfer is not None and transfer.poll() is None:
        transfer.terminate()
    if vm is not None and vm.poll() is None:
        try:
            with socket.socket(socket.AF_UNIX) as connection:
                connection.settimeout(2)
                connection.connect('/tmp/qemu-monitor.sock')
                connection.sendall(b'system_powerdown\n')
            vm.wait(timeout=105)
        except (OSError, subprocess.TimeoutExpired):
            vm.terminate()
            try:
                vm.wait(timeout=5)
            except subprocess.TimeoutExpired:
                vm.kill()
    if web is not None and web.poll() is None:
        web.terminate()


def main():
    global web
    os.umask(0o077)
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    shutil.copyfile(ROOT / 'index.html', TMP / 'index.html')
    publish()
    web = subprocess.Popen(['nginx', '-c', str(ROOT / 'nginx.conf'), '-g', 'daemon off;'])
    try:
        configure_and_start()
    except InterruptedError:
        pass
    except Exception as error:
        publish('failed', str(error), ready=False, percent=None)
        while not stop.wait(2):
            if web.poll() is not None:
                break
    finally:
        shutdown()


if __name__ == '__main__':
    main()
