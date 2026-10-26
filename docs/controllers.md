# Controller implementation notes

Controller support is not implemented in this package. The USB descriptor and
reports in `gadget.py` describe a keyboard only; this does not appear as a Pro
Controller to either Switch console.

There are two different extensions:

1. **Use a controller to drive keyboard input.** Read a connected controller on
   the Pi (for example through Linux input events), map selected buttons to HID
   keyboard usages and send balanced press/release reports through the existing
   keyboard endpoint. This still produces a keyboard at the console, so software
   must support keyboard input. Account for disconnects, repeats, simultaneous
   buttons, exclusive writers and a final all-released report.
2. **Present a controller to the console.** Implement a Switch-compatible
   controller protocol, including the appropriate report descriptors, input
   reports, host requests and initialization/handshake. A generic USB gamepad
   descriptor is not evidence of Switch Pro Controller compatibility. Specify
   which Switch generation and USB/Bluetooth transport you are implementing.

To expose keyboard and controller over the same USB cable, investigate one
**composite gadget** with two separate HID functions and descriptors, preserving
the keyboard's 8-byte report format on its own endpoint. Current ownership checks
intentionally reject extra functions, so this requires explicit code changes and
new tests. Do not have two independent gadget managers fight over the Pi's single
device controller. Successful enumeration alone does not verify game input.

A Bluetooth controller implementation is a separate transport with its own
pairing, HID profile and compatibility requirements; adding a USB endpoint does
not implement Bluetooth. Incoming physical-controller support and outgoing
console-controller emulation are separate responsibilities.

A capture card gives the computer a picture of the console. It does not deliver
keyboard or controller reports to the console. Keep the USB/Bluetooth input path
explicit even if the capture preview is where you watch the result.

The separate NXPS5/Pico controller project is not included here. No controller
compatibility, radio behavior or controller latency has been measured for this
keyboard package.
