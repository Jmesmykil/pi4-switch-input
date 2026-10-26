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
