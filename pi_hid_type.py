#!/usr/bin/env python3
"""Explicit ASCII text entry; no editor commands or program execution."""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import select
import signal
import stat
import sys
import time

NEUTRAL = bytes(8)


def encode(c, caps):
    if c.isascii() and c.isalpha():
        shift = c.isupper() != (caps == 'upper-default')
        return (2 if shift else 0, ord(c.lower()) - 97 + 4)
    if c in '1234567890':
        return (0, '1234567890'.index(c) + 30)
    if c in '!@#$%^&*()':
        return (2, '!@#$%^&*()'.index(c) + 30)
    if c == '\n':
        return (0, 40)
    if c == ' ':
        return (0, 44)
    low, high = '-=[]\\;\',./`', '_+{}|:\"<>?~'
    codes = (45, 46, 47, 48, 49, 51, 52, 54, 55, 56, 53)
    for a, b, key in zip(low, high, codes):
        if c in (a, b):
            return (2 if c == b else 0, key)
    raise ValueError(f'Unsupported character {c!r} (U+{ord(c):04X})')


def plan(text, file_mode, caps, initial_indent=0):
    encoded = [encode(c, caps) for c in text]
    if not file_mode:
        if '\n' in text:
            raise ValueError('--text test must contain no newline')
        return encoded
    result, inherited = [], initial_indent
    for line in text.splitlines(keepends=True):
        desired = len(line) - len(line.lstrip(' '))
        key = 42 if inherited > desired else 44
        result.extend([(0, key)] * abs(inherited - desired))
        inherited = desired
        result.extend(encode(c, caps) for c in line[desired:])
    return result


def write_report(fd, report, timeout=2.0):
    if len(report) != 8:
        raise ValueError('Keyboard reports must contain exactly 8 bytes')
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('HID report timed out')
        try:
            count = os.write(fd, report)
            if count != 8:
                raise OSError(f'Short HID report: {count}/8')
            return
        except BlockingIOError:
            try:
                ready = select.select([], [fd], [], remaining)[1]
            except InterruptedError:
                continue
            if not ready:
                raise TimeoutError('HID host is not accepting reports')
        except InterruptedError:
            continue


def send(device, strokes, delay_ms, enter_delay_ms, press_ms, progress=None):
    states = [p.read_text().strip() for p in Path('/sys/class/udc').glob('*/state')]
    if states != ['configured']:
        raise OSError(f'USB host is not configured: {states}')
    fd = os.open(device, os.O_WRONLY | os.O_NONBLOCK)
    valid_device = False
    locked = False
    try:
        valid_device = stat.S_ISCHR(os.fstat(fd).st_mode)
        if not valid_device:
            raise ValueError('Expected a HID character device')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        write_report(fd, NEUTRAL)
        completed_lines = 0
        for modifier, key in strokes:
            write_report(fd, bytes((modifier, 0, key, 0, 0, 0, 0, 0)))
            time.sleep(press_ms / 1000)
            write_report(fd, NEUTRAL)
            time.sleep((enter_delay_ms if key == 40 else delay_ms) / 1000)
            if key == 40 and progress is not None:
                completed_lines += 1
                progress(completed_lines)
    finally:
        try:
            if valid_device and locked:
                try:
                    write_report(fd, NEUTRAL)
                except OSError:
                    print('Final key release unconfirmed.', file=sys.stderr)
        finally:
            os.close(fd)


def interrupted(_signum, _frame):
    raise KeyboardInterrupt


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--text')
    source.add_argument('--file', type=Path)
    p.add_argument('--start-line', type=int)
    p.add_argument('--end-line', type=int)
    p.add_argument('--initial-indent', type=int, default=0)
    p.add_argument('--progress-lines', action='store_true')
    p.add_argument('--device', default='/dev/hidg0')
    p.add_argument('--caps-mode', required=True, choices=('normal', 'upper-default'))
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--delay-ms', type=float, default=50)
    p.add_argument('--enter-delay-ms', type=float, default=150)
    p.add_argument('--press-ms', type=float, default=50)
    p.add_argument('--backspace-count', type=int, default=0)
    a = p.parse_args(argv)
    try:
        if not all(math.isfinite(x) and 0 < x <= 10000
                   for x in (a.delay_ms, a.enter_delay_ms, a.press_ms)):
            raise ValueError('Delays must be greater than 0 and at most 10000 ms')
        if not 0 <= a.backspace_count <= 16 or (a.file is not None and a.backspace_count):
            raise ValueError('Backspaces are limited to 0..16 and text mode only')
        if a.file is None and (a.start_line is not None or a.end_line is not None
                               or a.initial_indent or a.progress_lines):
            raise ValueError('Line range and initial indent require --file')
        if not 0 <= a.initial_indent <= 256:
            raise ValueError('Initial indent must be within 0..256')
        raw = a.file.read_bytes() if a.file is not None else a.text.encode('ascii')
        source_sha256 = hashlib.sha256(raw).hexdigest()
        text = raw.decode('ascii')
        if a.file is not None:
            text = text.replace('\r\n', '\n')
            lines = text.splitlines(keepends=True)
            start = 1 if a.start_line is None else a.start_line
            end = len(lines) if a.end_line is None else a.end_line
            if not 1 <= start <= end <= len(lines):
                raise ValueError('Selected line range is outside the source file')
            text = ''.join(lines[start - 1:end])
        strokes = plan(text, a.file is not None, a.caps_mode, a.initial_indent)
        strokes = [(0, 42)] * a.backspace_count + strokes
        enters = sum(key == 40 for _, key in strokes)
        result = {'dry_run': a.dry_run, 'chars': len(text),
                  'backspaces': a.backspace_count,
                  'lines': len(text.splitlines()), 'final_newline': text.endswith('\n'),
                  'report_count': 2 * len(strokes) + 2,
                  'seconds_estimate': round((len(strokes) * a.press_ms
                                             + (len(strokes) - enters) * a.delay_ms
                                             + enters * a.enter_delay_ms) / 1000, 3),
                  'source_sha256': source_sha256,
                  'input_sha256': hashlib.sha256(text.encode('ascii')).hexdigest(),
                  'initial_indent': a.initial_indent,
                  'source_lines': [start, end] if a.file is not None else None,
                  'cursor_plan': 'next line' if text.endswith('\n') else 'end of text'}
        if not a.dry_run:
            for signum in (signal.SIGTERM, signal.SIGHUP):
                signal.signal(signum, interrupted)
            def progress(completed):
                print(json.dumps({'event': 'line_dispatched',
                                  'input_line': start + completed - 1,
                                  'visual_verification': False}),
                      file=sys.stderr, flush=True)

            send(a.device, strokes, a.delay_ms, a.enter_delay_ms, a.press_ms,
                 progress if a.progress_lines else None)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Interrupted; target text may be partial.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
