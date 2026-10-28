# Pi 4 → Switch input

The keyboard method from my Raspberry Pi 4 setup, packaged separately so it can
be read and implemented elsewhere. The Pi presents a standard USB boot keyboard;
Python sends 8-byte press/release reports to `/dev/hidg0`.

```text
Computer ── SSH over Ethernet/Wi-Fi ── Pi 4 USB-C ── USB data cable/hub ── Switch 2
```

Two input paths are available:

- **USB keyboard:** the code and setup below are included in this repository.
- **Bluetooth Pro Controller:** a [tested setup guide](docs/controllers.md) uses the
  external Seedsow Lua Editor bridge and pinned NXBT source. It covers pairing as
  Player 1, navigation, calibration and Lua uploads. Controller runtime code remains
  in those upstream projects; this repository does not bundle it.

The capture card supplies a view of the console; it does not carry these inputs.

This is a cleaned extraction of the original input method. Host tests cover
report generation and ownership checks. The extracted USB keyboard package has not been tested
on a physical Switch 2. The separate Bluetooth route was verified on Switch 2 on
2026-10-27; its [evidence and limits](docs/controllers.md#verified-hardware-result)
are recorded separately. A successful HID write means the host accepted a report;
check the actual text on screen before sending more.

## What you need

- Raspberry Pi 4 running Raspberry Pi OS/Linux with Python 3, `dwc2`,
  `libcomposite`, configfs and the HID gadget function. No pip packages required.
- The Pi's **USB-C peripheral/OTG port** and a data-capable cable to the console's
  USB host port. The Pi's USB-A ports are host ports, not the gadget connection.
- Ethernet or Wi-Fi access to the Pi to run commands.
- A suitable power arrangement. Do not assume the console/hub supplies enough
  current for a Pi 4. Follow the [official Pi OTG guide] rather than improvising
  power backfeeding or connecting two power supplies together.

The original working wiring record used a single hub at the bottom USB
connection. This describes that setup, not a universal hub or port requirement.
Start with a short data cable and inspect `status` if the host does not enumerate.

## Prepare the Pi

The following commands run on the Pi, after downloading/cloning this directory.
Keep a backup of your boot configuration. In `/boot/firmware/config.txt` (older
images may use `/boot/config.txt`), add this under an `[all]` section:

```ini
[all]
dtoverlay=dwc2,dr_mode=peripheral
```

Review any existing USB gadget/OTG settings first. Reboot the Pi normally to load
the overlay. The scripts do not edit boot files or reboot the Pi for you.

Check configfs and mount it only if it is not already mounted:

```sh
findmnt /sys/kernel/config
# Only if the command above shows no mount:
sudo mount -t configfs none /sys/kernel/config
```

Connect the USB data path, then create the keyboard:

```sh
sudo python3 gadget.py start
python3 gadget.py status
```

`start` loads the two kernel modules, creates only `pi4_switch_keyboard`, selects
**full-speed** before binding and expects a single controller and `/dev/hidg0`.
It refuses to replace another gadget or HID node. It also refuses to reuse a
gadget with different identity, descriptor or function settings. `stop` checks
the same ownership before removing anything.

`status` should show `configured` and `full-speed` when the console accepts the
USB connection. No controller means the peripheral overlay is not available;
`not attached`/`powered` instead of `configured` points to the cable, host or USB
connection. An existing gadget requires inspection, not forced removal.

## Send a small text test

Open an editable text field on the console and place its cursor deliberately.
Preview the character mapping without touching USB:

```sh
python3 pi_hid_type.py --text 'Hello 123!' --caps-mode normal --dry-run
```

Then send the same text:

```sh
sudo python3 pi_hid_type.py --text 'Hello 123!' --caps-mode normal
```

Mapping is US keyboard ASCII. `normal` means unshifted letters appear lowercase.
Use `--caps-mode upper-default` only when the target editor produces uppercase
letters by default; it reverses Shift for letters, not for punctuation. This is
not automatic keyboard-layout or Caps Lock detection. Unicode and tabs are
rejected before any reports are sent.

Each key is followed by a neutral release report. The sender takes an exclusive
advisory device lock, uses bounded nonblocking writes and attempts a final release
on errors or interruption. Other programs must respect the same lock. Disconnects
can prevent the final release reaching the host; inspect the target after errors.

## Send a text file to an auto-indenting editor

Create `example.txt` with your own ASCII text before running these commands:

```sh
python3 pi_hid_type.py --file example.txt --caps-mode normal --dry-run
sudo python3 pi_hid_type.py --file example.txt --caps-mode normal --progress-lines
```

**File mode assumes the editor carries the previous line's leading spaces onto
the next line.** It adds/removes spaces to reach each line's desired indentation.
Use it only with that auto-indent behavior and a known cursor position. It can
produce incorrect indentation in a plain text field that does not auto-indent.
It normalizes CRLF line endings; a final newline sends Enter. The sender does not
read the screen or know whether Enter commits/submits something in the target UI.

For a partial resend, `--start-line 2 --end-line 4` selects inclusive source lines;
`--initial-indent 4` describes spaces already present at the starting cursor.
The default assumes zero inherited indentation. Progress reports count lines
dispatched, not lines visually verified.

Defaults are 50 ms key press, 50 ms between ordinary keys and 150 ms after Enter.
Adjust with `--press-ms`, `--delay-ms`, and `--enter-delay-ms` after a small test.
`--backspace-count N` allows 0 to 16 leading backspaces in `--text` mode only. See
`python3 pi_hid_type.py --help` for all options.

## Stop and undo

```sh
sudo python3 gadget.py stop
```

This unbinds and removes only this package's matching configfs gadget. To undo
peripheral boot setup, remove only the overlay line you added and reboot. Preserve
other boot settings and any pre-existing configfs mount.

Optional automatic startup uses the supplied service and a fixed install path:

```sh
sudo install -d /opt/pi4-switch-input
sudo install -m 0644 gadget.py pi_hid_type.py /opt/pi4-switch-input/
sudo install -m 0644 systemd/pi4-switch-keyboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pi4-switch-keyboard.service
```

Use this only after manual startup works. It does not send text. To remove it:

```sh
sudo systemctl disable --now pi4-switch-keyboard.service
sudo rm /etc/systemd/system/pi4-switch-keyboard.service
sudo systemctl daemon-reload
```

The two installed Python files can then be removed from `/opt/pi4-switch-input`
after confirming they are the copies you installed.

## Develop

```sh
python3 -m unittest discover -s tests -v
```

Tests mock the gadget/device boundary and do not configure USB or send input.
[Provenance](PROVENANCE.md) records the extraction. Released under the
[MIT License](LICENSE), allowing reuse and modification with the license notice
preserved.

[official Pi OTG guide]: https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-009276-WP-1-Using%20OTG%20mode%20on%20Raspberry%20Pi%20SBCs

Protocol reference: [Linux HID gadget documentation](https://docs.kernel.org/usb/gadget_hid.html).
