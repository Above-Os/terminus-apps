"""Architecture-specific QEMU configuration; KVM remains mandatory in production."""
from pathlib import Path
import platform
import shutil


def architecture(machine=None):
    machine = (machine or platform.machine()).lower()
    aliases = {'x86_64': 'amd64', 'amd64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}
    if machine not in aliases:
        raise ValueError('Only amd64 and arm64 hosts are supported.')
    return aliases[machine]


def check_disk_architecture(arch, image, marker):
    if marker.exists():
        if marker.read_text().strip() != arch:
            raise RuntimeError('The existing disk belongs to another CPU architecture. Use a separate installation.')
    elif image.exists():
        if arch != 'amd64':
            raise RuntimeError('Existing disk architecture is unknown. A legacy x86 disk cannot be reused on ARM.')
        marker.write_text('amd64\n')


def prepare_firmware(arch, store, firmware=Path('/usr/share/AAVMF')):
    if arch != 'arm64':
        return
    code, template = firmware / 'AAVMF_CODE.fd', firmware / 'AAVMF_VARS.fd'
    if not code.is_file() or not template.is_file():
        raise RuntimeError('ARM64 UEFI firmware is missing from the container image.')
    variables = store / 'uefi-vars.fd'
    if not variables.exists():
        shutil.copyfile(template, variables)
        variables.chmod(0o600)
    elif variables.stat().st_size != template.stat().st_size:
        raise RuntimeError('Stored ARM UEFI variables do not match the installed firmware layout.')


def command(arch, cpu, memory, image, store, firmware=Path('/usr/share/AAVMF')):
    if arch == 'amd64':
        args = ['qemu-system-x86_64', '-enable-kvm', '-machine', 'q35', '-cpu', 'host',
                '-smp', str(cpu), '-m', str(memory * 1024),
                '-drive', f'file={image},format=qcow2,if=virtio',
                '-drive', 'file=/tmp/seed.iso,format=raw,media=cdrom,readonly=on']
    elif arch == 'arm64':
        args = ['qemu-system-aarch64', '-enable-kvm', '-machine', 'virt,gic-version=host',
                '-cpu', 'host', '-smp', str(cpu), '-m', str(memory * 1024),
                '-drive', f'if=pflash,format=raw,unit=0,readonly=on,file={firmware / "AAVMF_CODE.fd"}',
                '-drive', f'if=pflash,format=raw,unit=1,file={store / "uefi-vars.fd"}',
                '-drive', f'file={image},format=qcow2,if=none,id=osdisk',
                '-device', 'virtio-blk-pci,drive=osdisk,bootindex=1',
                '-drive', 'file=/tmp/seed.iso,format=raw,if=none,id=seed,readonly=on',
                '-device', 'virtio-scsi-pci,id=seedscsi',
                '-device', 'scsi-cd,drive=seed,bus=seedscsi.0',
                '-device', 'virtio-gpu-pci', '-device', 'virtio-rng-pci', '-device', 'qemu-xhci,id=usb',
                '-device', 'usb-kbd,bus=usb.0', '-device', 'usb-tablet,bus=usb.0']
    else:
        raise ValueError('Unsupported CPU architecture.')
    return args + ['-netdev', 'user,id=net0,hostfwd=tcp:0.0.0.0:22-:22,hostfwd=tcp:0.0.0.0:2222-:22',
        '-device', 'virtio-net-pci,netdev=net0' + (',romfile=' if arch == 'arm64' else ''),
        '-vnc', '127.0.0.1:0,websocket=5700',
        '-serial', 'file:/tmp/serial.log', '-monitor', 'unix:/tmp/qemu-monitor.sock,server=on,wait=off',
        '-device', 'virtio-serial', '-chardev', 'socket,path=/tmp/qga.sock,server=on,wait=off,id=qga0',
        '-device', 'virtserialport,chardev=qga0,name=org.qemu.guest_agent.0']
