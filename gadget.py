#!/usr/bin/env python3
"""Manage this package's USB boot keyboard; never send keystrokes."""
import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT = Path('/sys/kernel/config/usb_gadget')
UDC_ROOT = Path('/sys/class/udc')
DEV_ROOT = Path('/dev')
GADGET = ROOT / 'pi4_switch_keyboard'
SERIAL = 'PI4-SWITCH-KEYBOARD-1'
DESCRIPTOR = bytes.fromhex(
    '05010906a101050719e029e715002501750195088102950175088103'
    '95057501050819012905910295017503910395067508150025650507'
    '190029658100c0'
)
IDENTITY = {'serialnumber': SERIAL, 'manufacturer': 'Pi4 Switch Input',
            'product': 'Pi USB Keyboard'}


def put(path, value):
    path.write_bytes(value if isinstance(value, bytes) else str(value).encode())


def assert_owned():
    """Refuse changed or unrelated gadgets before touching their binding."""
    try:
        if GADGET.is_symlink():
            raise ValueError('Gadget path is a symlink')
        for relative in ('strings', 'strings/0x409', 'functions', 'configs',
                         'configs/c.1', 'configs/c.1/strings',
                         'configs/c.1/strings/0x409'):
            if (GADGET / relative).is_symlink():
                raise ValueError(f'Unexpected directory link: {relative}')
        for relative in ('strings', 'configs/c.1/strings'):
            if {p.name for p in (GADGET / relative).iterdir()} != {'0x409'}:
                raise ValueError('Unexpected string languages')
        for name, expected in IDENTITY.items():
            if (GADGET / 'strings/0x409' / name).read_text().strip() != expected:
                raise ValueError(f'Unexpected {name}')
        for name, expected in {'idVendor': 0x1d6b, 'idProduct': 0x0104}.items():
            if int((GADGET / name).read_text().strip(), 16) != expected:
                raise ValueError(f'Unexpected {name}')
        if {p.name for p in (GADGET / 'functions').iterdir()} != {'hid.usb0'}:
            raise ValueError('Unexpected USB functions')
        if {p.name for p in (GADGET / 'configs').iterdir()} != {'c.1'}:
            raise ValueError('Unexpected configurations')
        function = GADGET / 'functions/hid.usb0'
        if function.is_symlink() or (function / 'report_desc').read_bytes() != DESCRIPTOR:
            raise ValueError('Unexpected keyboard descriptor')
        for name, expected in {'subclass': 1, 'protocol': 1, 'report_length': 8}.items():
            if int((function / name).read_text().strip()) != expected:
                raise ValueError(f'Unexpected {name}')
        link = GADGET / 'configs/c.1/hid.usb0'
        if not link.is_symlink() or link.resolve() != function.resolve():
            raise ValueError('Unexpected keyboard configuration link')
        links = {p.name for p in link.parent.iterdir() if p.is_symlink()}
        if links != {'hid.usb0'}:
            raise ValueError('Unexpected configuration links')
    except (OSError, ValueError) as error:
        raise RuntimeError(f'Preserving gadget: ownership check failed ({error})') from error


def status():
    controllers = []
    for controller in sorted(UDC_ROOT.glob('*')):
        row = {'name': controller.name}
        for field in ('state', 'current_speed', 'maximum_speed'):
            path = controller / field
            row[field] = path.read_text().strip() if path.exists() else None
        controllers.append(row)
    print(json.dumps({'controllers': controllers,
                      'gadget_exists': GADGET.exists(),
                      'bound_to': (GADGET / 'UDC').read_text().strip()
                      if (GADGET / 'UDC').exists() else None,
                      'hid_devices': [str(p) for p in DEV_ROOT.glob('hidg*')]}, indent=2))


def _remove_created():
    """Remove only named paths created by this package, including partial starts."""
    binding = GADGET / 'UDC'
    if binding.exists() and binding.read_text().strip():
        put(binding, '\n')
    link = GADGET / 'configs/c.1/hid.usb0'
    if link.is_symlink():
        link.unlink()
    for relative in ('configs/c.1/strings/0x409', 'configs/c.1',
                     'functions/hid.usb0', 'strings/0x409'):
        path = GADGET / relative
        if path.exists():
            path.rmdir()
    GADGET.rmdir()


def start():
    subprocess.run(['modprobe', 'dwc2'], check=True, timeout=15)
    subprocess.run(['modprobe', 'libcomposite'], check=True, timeout=15)
    if not ROOT.exists():
        raise RuntimeError('Mount configfs first; see README.md')
    controllers = list(UDC_ROOT.glob('*'))
    if len(controllers) != 1:
        raise RuntimeError(f'Expected one USB device controller, found {len(controllers)}')
    controller = controllers[0].name
    for other in ROOT.iterdir():
        if other != GADGET:
            raise RuntimeError(f'Preserving existing gadget: {other.name}')
    if GADGET.exists() or GADGET.is_symlink():
        assert_owned()
        if (GADGET / 'UDC').read_text().strip() != controller:
            raise RuntimeError('Existing unbound gadget; inspect before restarting')
        if (GADGET / 'max_speed').read_text().strip() != 'full-speed':
            raise RuntimeError('Existing gadget is not set to full-speed; inspect before restarting')
        status()
        return
    if list(DEV_ROOT.glob('hidg*')):
        raise RuntimeError('Preserving existing HID device nodes')
    GADGET.mkdir()
    try:
        for name, value in {'idVendor': '0x1d6b', 'idProduct': '0x0104',
                            'bcdUSB': '0x0200', 'bcdDevice': '0x0100',
                            'bDeviceClass': '0', 'bDeviceSubClass': '0',
                            'bDeviceProtocol': '0'}.items():
            put(GADGET / name, value)
        strings = GADGET / 'strings/0x409'
        strings.mkdir()
        for name, value in IDENTITY.items():
            put(strings / name, value)
        config = GADGET / 'configs/c.1'
        config.mkdir()
        put(config / 'MaxPower', '500')
        config_strings = config / 'strings/0x409'
        config_strings.mkdir()
        put(config_strings / 'configuration', 'Keyboard')
        function = GADGET / 'functions/hid.usb0'
        function.mkdir()
        for name, value in {'subclass': '1', 'protocol': '1',
                            'report_length': '8', 'report_desc': DESCRIPTOR}.items():
            put(function / name, value)
        (config / 'hid.usb0').symlink_to(function)
        # Preserve the connection speed used by the original Pi 4 setup.
        if not (GADGET / 'max_speed').exists():
            raise RuntimeError('Kernel has no gadget max_speed setting')
        put(GADGET / 'max_speed', 'full-speed')
        put(GADGET / 'UDC', controller)
    except BaseException:
        _remove_created()
        raise
    for _ in range(30):
        if (DEV_ROOT / 'hidg0').exists():
            break
        time.sleep(0.1)
    if sorted(p.name for p in DEV_ROOT.glob('hidg*')) != ['hidg0']:
        stop()
        raise RuntimeError('Expected this keyboard to create only /dev/hidg0')
    status()


def stop():
    if not GADGET.exists() and not GADGET.is_symlink():
        return
    assert_owned()
    _remove_created()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'stop', 'status'))
    args = parser.parse_args()
    try:
        {'start': start, 'stop': stop, 'status': status}[args.action]()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f'Error: {error}\n')
