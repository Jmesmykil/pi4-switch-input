# Source provenance

Extracted 2026-10-26 from the author's existing Pi 4 local input tools. Only the
keyboard transport and text sender are included. Source snapshot checksums:

| Original filename | SHA-256 |
| --- | --- |
| `gadget.py` | `eea96a6fd1305246ae38e5e862ad9506213a50a3188f771796a09994e6234faf` |
| `pi_hid_type.py` | `a0a0e5376586367cac4875038e969515f4922e1f07fb63b87e94a07cdfca9f8c` |
| `pi_hb_prepare.py` (full-speed setting only) | `b87d407d7751fd3d042eb01d5724e9129fa5bbea35b622bbf41ae67c0fa5fce7` |

Changes for sharing:

- Generic gadget name, USB strings and service install path.
- Ownership/descriptor/function checks before both start and stop.
- The original full-speed setting is applied directly before USB binding.
- Original ASCII mapping, auto-indent planner and timing controls retained.
- Report-length validation and testable argument parsing added to the sender.
- Setup/removal instructions, controller design notes and host-only tests added.

The available input source snapshot had no standalone license notice. This
extracted package is released under the [MIT License](LICENSE), selected by the
author for reuse and modification. Public protocol documentation is linked for
reference, not bundled.


## Bluetooth guide (2026-10-27)

`docs/controllers.md` now documents an independently exercised integration with
DialingSpoon527/seedsow-lua-editor at commit
`138c752856bebdfcd92ac07fa5e6dd67f99a5f50`. Its installer, bridge, pairing agent,
NXBT patcher and packet protocol were compared byte-for-byte with that commit
before documenting the tested setup. The installer pins Brikwerk/nxbt commit
`ec4b800ad6c55de96bb6c7f9f84b5bdc59a4c975` and applies its documented compatibility
fixes. Those projects' runtime source is linked, not copied into this repository;
their own licenses and third-party notices apply.

Hardware observations cover Player 1 pairing, controller navigation, calibration,
a checksummed 228-byte raw Lua upload and its visible Lua 5.1 output. They do not
establish USB controller support or automatic reconnect across restarts. The
original extracted USB package's separate hardware-testing limitation remains.
