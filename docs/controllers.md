# Pi Bluetooth Pro Controller setup

This guide documents the Bluetooth path verified on Switch 2 on 2026-10-27.
It uses the external [Seedsow Lua Editor bridge][seedsow] and [NXBT][nxbt].
The USB keyboard code in this repository remains a keyboard; adding this bridge
uses the Pi's Bluetooth adapter and leaves the existing USB gadget alone.

```text
Computer ── SSH over Ethernet/Wi-Fi ── Pi 4 ── Bluetooth Pro Controller ── Switch 2
```

Pairing and ordinary controller buttons do not require Seedsow. The framed Lua
upload receiver described below **does** require an already installed, compatible
Seedsow Lua Editor. Installing the Pi bridge does not install that console editor.
The capture card supplies a view for verification; it carries no controller input.

## Install the bridge on the Pi

Requirements: Raspberry Pi OS/Debian, a supported Bluetooth adapter, Python 3,
network access for installation, and sudo access. The verified Pi ran Debian 13
with Python 3.13.5 and BlueZ 5.82. Other adapters and OS versions need their own
pairing/input check. A USB gadget/OTG cable is not required for Bluetooth input.

Run on the Pi from a new working directory:

```sh
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/DialingSpoon527/seedsow-lua-editor.git
cd seedsow-lua-editor
git checkout --detach 138c752856bebdfcd92ac07fa5e6dd67f99a5f50
sudo sh pi/install.sh
systemctl is-active seedsow-input
```

The installer installs Git, Python D-Bus/GObject bindings, BlueZ and rfkill; fetches
NXBT revision `ec4b800ad6c55de96bb6c7f9f84b5bdc59a4c975`; applies the upstream
D-Bus/report-loop compatibility fixes; and enables `seedsow-input.service` at boot.
Installed code lives in `/opt/seedsow-input`. The bridge configuration and generated
token live in root-only `/etc/seedsow-input.json`. Reinstallation preserves that
token but stops an existing bridge/transfer, so reuse a working installation.

The bridge listens on LAN port 39391 using bearer-authenticated HTTP, without TLS.
Use a trusted LAN and keep that port off the public internet. The console receives
Bluetooth controller reports; it does not need Wi-Fi or Nintendo connectivity for
these inputs. Airplane mode can stay on with its Bluetooth/controller exception.

The upstream Windows companion can import a private connection file exported by
`python3 pi/export_connection.py --output ~/seedsow-connection.json`; see its
[Pi setup guide][pi-guide]. Keep that file private. The command-line examples here
run on the Pi and read its token locally, so no token needs to be copied to chat
or placed in a command argument.

## Pair as Player 1

1. Put other nearby Switch consoles to sleep.
2. On the target console, open **Controllers → Change Grip/Order**. Enable
   Bluetooth/controller communication if airplane mode is on.
3. On the Pi, define this helper in your current shell. It calls only the local
   bridge and never prints its token:

   ```sh
   bridge() {
       sudo python3 - "$@" <<'PY'
   import json
   import sys
   import urllib.request

   with open('/etc/seedsow-input.json') as source:
    config = json.load(source)
   body = None if len(sys.argv) == 2 else sys.argv[2].encode('utf-8')
   request = urllib.request.Request(
    'http://127.0.0.1:' + str(config['port']) + sys.argv[1],
    data=body,
    headers={'Authorization': 'Bearer ' + config['token'],
             'Content-Type': 'application/json'})
   with urllib.request.urlopen(request, timeout=25) as response:
    print(response.read().decode('utf-8'))
   PY
   }
   ```

4. Start pairing once, then read status:

   ```sh
   bridge /pair '{"reset":false}'
   bridge /status
   ```

   Pairing may initially report `connecting`. Wait for `connected`,
   `"player_number": 1` and `"errors": false`, and check the Pro Controller on
   the console screen. The bridge's pairing agent accepts Nintendo Switch named
   devices during a ten-minute window. If another controller occupies Player 1,
   use Change Grip/Order to assign the Pi first before attempting uploads.
5. The Pi can now press buttons, including leaving the pairing screen with A:

   ```sh
   bridge /tap '{"button":"A"}'
   ```

If status reports `crashed` or an old controller must be removed, return the console
to Change Grip/Order and explicitly request `bridge /pair '{"reset":true}'`.
Resetting removes the previous bridge controller; do not reset during a transfer.

## Navigate the editor

Return to the running Seedsow Lua Editor. Example taps:

```sh
bridge /tap '{"button":"DPAD_DOWN"}'
bridge /tap '{"button":"DPAD_RIGHT"}'
bridge /tap '{"button":"A"}'
```

Allow each tap to finish and check the selected item before activating it.
`queued:true` means a button was queued; it does not establish the resulting UI
state. Supported names are `A`, `B`, `X`, `Y`, `L`, `R`, `ZL`, `ZR`, `PLUS`,
`MINUS`, and `DPAD_UP`, `DPAD_DOWN`, `DPAD_LEFT`, `DPAD_RIGHT`.

In the editor, **Y** runs the buffer, **B** returns from a normally running
program, and the D-pad plus A selects toolbar actions. During packet reception,
buttons carry data and ordinary navigation is disabled.

## Calibrate the upload receiver once

1. Select **Calibrate input** in the already installed console editor. Do not
   assume a particular save slot: use your working editor entry. The verified
   installation used slot 3; standard upstream packages may use slot 2 for input.
2. Confirm the console says **INPUT CALIBRATION**, waiting for physical A.
3. Release every other controller, then run:

   ```sh
   bridge /calibrate '{}'
   ```

4. The Pi sends A, B, X, Y, L, R with holds and releases, taking about 18 seconds.
   Confirm **PC INPUT: 0 / ? bytes** on the console. An old “hold physical R”
   heading may remain above that status; the zero-count receiver is the useful
   confirmation. The bridge's `calibration inputs sent` alone is not confirmation.

The editor saves its measured button mappings. On later uploads, select
**Receive PC** and confirm a fresh zero count; do not recalibrate or reinstall a
working bridge for every file.

## Send a small Lua probe

Create `probe01.lua` on the Pi with these exact contents, including the final
newline:

```lua
print("Lua:",_VERSION)
print("Engine:",type(e))
print("IO:",type(io),"OS:",type(os))
print("Debug:",type(debug),"Package:",type(package))
print("FFI:",type(ffi),"JIT:",type(jit))
print("Engine metatable:",type(getmetatable(e)))
```

With the console at **PC INPUT: 0 / ? bytes**, run this from the external
`seedsow-lua-editor` checkout. It uses that project's validated packet builder:

```sh
sudo python3 - probe01.lua <<'PY'
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path('pc').resolve()))
from client import upload_request

path = Path(sys.argv[1])
payload, estimate = upload_request(path.name, path.read_bytes(), slot=None)
with open('/etc/seedsow-input.json') as source:
    config = json.load(source)
request = urllib.request.Request(
    'http://127.0.0.1:' + str(config['port']) + '/send',
    data=json.dumps(payload).encode('utf-8'),
    headers={'Authorization': 'Bearer ' + config['token'],
             'Content-Type': 'application/json'})
with urllib.request.urlopen(request, timeout=25) as response:
    print(response.read().decode('utf-8'))
print('Estimated transfer seconds:', round(estimate))
PY
```

`slot=None` uses **raw file mode**: it saves `probe01.lua` and loads that source
into the editor buffer without publishing a numbered program slot or replacing
`sscode004.lua`. Choose a fresh filename for later probes; sending a filename
again writes that file. The upstream receiver backs up readable prior contents
as `.bak` and checks writes by readback. Keep editor/recovery files protected.

At Normal speed this 228-byte file takes about 100 seconds. Keep other controls
released. Read progress with `bridge /status`, but wait for the **console** to show:

```text
PC FILE SAVED: probe01.lua / 228 bytes / 44A94905. L returns.
```

The hex value is the source Adler32 checksum. `input sent` from the Pi only means
transmission finished; a console checksum/filename/byte-count match is required.
Then leave the receiver and run the buffer, waiting for the first action to finish
before the second:

```sh
bridge /tap '{"button":"L","down":1.0,"up":0.3}'
# After the receiver closes:
bridge /tap '{"button":"Y"}'
```

Use a compatible editor's **Save + publish** in a free user slot only when you
want a normal load-menu entry. Raw upload already saves the source file; this
example deliberately does not publish a numbered save slot.

## Cancel, stop and reconnect

- `bridge /stop '{}'` cancels transmission on the Pi. Hold L on the console to
  leave its receiver, then enter **Receive PC** again at zero before a new upload.
  Never resume from an uncertain partial byte count.
- `sudo systemctl stop seedsow-input` stops the bridge and disconnects its
  controller. `sudo systemctl start seedsow-input` starts the service again.
- Check `systemctl status seedsow-input --no-pager` and
  `sudo journalctl -u seedsow-input -n 60 --no-pager` for local diagnostics.
- Service installation enables startup at Pi boot. Automatic controller reconnect
  after a Pi/service/console restart has not been verified; check status and pair
  from Change Grip/Order if needed.

Do not remove or reconfigure the USB keyboard gadget to troubleshoot Bluetooth.
The transports are separate. A system text-entry test through the existing USB
keyboard produced incomplete text during this session; the calibrated Bluetooth
packet receiver successfully transferred the complete source instead.

## Verified hardware result

On 2026-10-27 the installed upstream bridge, with the pinned NXBT revision above,
paired a Pi as Player 1 on Switch 2. Capture-card observations confirmed controller
navigation into the running Seedsow editor, calibration, the 228-byte raw-file
receipt with checksum `44A94905`, and execution with the editor's Guard enabled.
The visible result was:

- Lua 5.1; engine exposed as `userdata`.
- `io`, `os`, `debug` and `package` exposed as tables.
- No global `ffi` or `jit` (`nil`).

The sixth metatable print was below the visible output preview and was not
independently observed in this first probe. Library/table presence does not prove
which functions work. No arbitrary native execution, NRO loading or system access
was established by this probe. This records the external Bluetooth integration;
it does not qualify this repository's extracted USB keyboard package on hardware.

## Other controller extensions

A physical controller connected to the Pi could separately drive USB keyboard
reports, but the console would still see a keyboard. A USB Pro Controller or
composite keyboard/controller gadget would require a different descriptor,
protocol, handshake and tests; that is not implemented here. The current gadget
ownership checks intentionally reject extra functions. Do not run independent
gadget managers against the Pi's single USB device controller.

The separate NXPS5/Pico project is not included in this package.

[seedsow]: https://github.com/DialingSpoon527/seedsow-lua-editor/tree/138c752856bebdfcd92ac07fa5e6dd67f99a5f50
[nxbt]: https://github.com/Brikwerk/nxbt/tree/ec4b800ad6c55de96bb6c7f9f84b5bdc59a4c975
[pi-guide]: https://github.com/DialingSpoon527/seedsow-lua-editor/blob/138c752856bebdfcd92ac07fa5e6dd67f99a5f50/docs/02-pi-setup.md
