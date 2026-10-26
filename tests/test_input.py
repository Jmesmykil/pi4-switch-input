import contextlib
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

import gadget
import pi_hid_type as hid


class EncodingTests(unittest.TestCase):
    def test_us_letter_number_and_punctuation_mapping(self):
        self.assertEqual(hid.encode('a', 'normal'), (0, 4))
        self.assertEqual(hid.encode('A', 'normal'), (2, 4))
        self.assertEqual(hid.encode('0', 'normal'), (0, 39))
        self.assertEqual(hid.encode('!', 'normal'), (2, 30))
        self.assertEqual(hid.encode('?', 'normal'), (2, 56))
        self.assertEqual(hid.encode('\\', 'normal'), (0, 49))

    def test_upper_default_changes_letters_only(self):
        self.assertEqual(hid.encode('A', 'upper-default'), (0, 4))
        self.assertEqual(hid.encode('a', 'upper-default'), (2, 4))
        self.assertEqual(hid.encode('!', 'upper-default'), (2, 30))

    def test_reject_unsupported_characters_and_text_newlines(self):
        for char in ('\t', '\r', 'é', '\x00'):
            with self.subTest(char=char), self.assertRaises(ValueError):
                hid.plan(char, False, 'normal')
        with self.assertRaises(ValueError):
            hid.plan('a\nb', False, 'normal')

    def test_auto_indent_adds_then_removes_inherited_spaces(self):
        strokes = hid.plan('  a\n b\nc', True, 'normal')
        self.assertEqual(strokes, [(0, 44), (0, 44), (0, 4), (0, 40),
                                   (0, 42), (0, 5), (0, 40), (0, 42), (0, 6)])

    def test_initial_indent_is_cursor_state(self):
        self.assertEqual(hid.plan(' a', True, 'normal', 3),
                         [(0, 42), (0, 42), (0, 4)])

    def test_file_range_crlf_and_dry_run_do_not_send(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'example.txt'
            source.write_bytes(b'first\r\n  second\r\nthird\r\n')
            out = io.StringIO()
            with contextlib.redirect_stdout(out), mock.patch.object(hid, 'send') as send:
                result = hid.main(['--file', str(source), '--start-line', '2',
                                   '--end-line', '2', '--caps-mode', 'normal', '--dry-run'])
            self.assertEqual(result, 0)
            send.assert_not_called()
            summary = json.loads(out.getvalue())
            self.assertEqual(summary['source_lines'], [2, 2])
            self.assertEqual(summary['chars'], len('  second\n'))
            self.assertTrue(summary['final_newline'])

    def test_invalid_timing_and_backspaces_never_send(self):
        for option in (['--delay-ms', 'nan'], ['--press-ms', '0'],
                       ['--enter-delay-ms', '10001'], ['--backspace-count', '17']):
            with self.subTest(option=option), contextlib.redirect_stderr(io.StringIO()), \
                    mock.patch.object(hid, 'send') as send:
                self.assertEqual(hid.main(['--text', 'a', '--caps-mode', 'normal'] + option), 1)
                send.assert_not_called()


class ReportTests(unittest.TestCase):
    def test_report_length_rejected_before_write(self):
        with mock.patch.object(hid.os, 'write') as write:
            with self.assertRaises(ValueError):
                hid.write_report(3, bytes(7))
            write.assert_not_called()

    def test_short_write_fails(self):
        with mock.patch.object(hid.os, 'write', return_value=4):
            with self.assertRaisesRegex(OSError, 'Short HID'):
                hid.write_report(3, bytes(8))

    def test_backpressure_has_bounded_timeout(self):
        with mock.patch.object(hid.os, 'write', side_effect=BlockingIOError), \
                mock.patch.object(hid.select, 'select', return_value=([], [], [])):
            with self.assertRaisesRegex(TimeoutError, 'not accepting'):
                hid.write_report(3, bytes(8), 0.1)

    def run_sender(self, side_effect=None):
        state = mock.Mock()
        state.read_text.return_value = 'configured\n'
        with mock.patch.object(hid.Path, 'glob', return_value=[state]), \
                mock.patch.object(hid.os, 'open', return_value=3), \
                mock.patch.object(hid.os, 'fstat', return_value=mock.Mock(st_mode=stat.S_IFCHR)), \
                mock.patch.object(hid.os, 'close') as close, \
                mock.patch.object(hid.fcntl, 'flock'), \
                mock.patch.object(hid.time, 'sleep'), \
                mock.patch.object(hid, 'write_report', side_effect=side_effect) as write:
            if side_effect:
                with self.assertRaises(KeyboardInterrupt):
                    hid.send('/dev/test', [(2, 4)], 1, 1, 1)
            else:
                hid.send('/dev/test', [(2, 4)], 1, 1, 1)
            calls = [args.args[1] for args in write.call_args_list]
            close.assert_called_once_with(3)
        return calls

    def test_press_is_followed_by_neutral_release(self):
        self.assertEqual(self.run_sender(), [bytes(8), bytes((2, 0, 4, 0, 0, 0, 0, 0)),
                                             bytes(8), bytes(8)])

    def test_interrupt_attempts_release_and_closes_device(self):
        calls = self.run_sender([None, KeyboardInterrupt(), None])
        self.assertEqual(calls[-1], bytes(8))


class GadgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.root, self.udc, self.dev = root / 'gadgets', root / 'udc', root / 'dev'
        for path in (self.root, self.udc, self.dev):
            path.mkdir()
        self.path = self.root / 'pi4_switch_keyboard'
        for key, value in {'ROOT': self.root, 'UDC_ROOT': self.udc,
                           'DEV_ROOT': self.dev, 'GADGET': self.path}.items():
            patch = mock.patch.object(gadget, key, value)
            patch.start()
            self.addCleanup(patch.stop)

    def owned_fixture(self):
        (self.path / 'strings/0x409').mkdir(parents=True)
        (self.path / 'functions/hid.usb0').mkdir(parents=True)
        (self.path / 'configs/c.1/strings/0x409').mkdir(parents=True)
        for name, value in gadget.IDENTITY.items():
            (self.path / 'strings/0x409' / name).write_text(value)
        for name, value in {'idVendor': '0x1d6b', 'idProduct': '0x0104',
                            'UDC': 'controller', 'max_speed': 'full-speed'}.items():
            (self.path / name).write_text(value)
        function = self.path / 'functions/hid.usb0'
        (function / 'report_desc').write_bytes(gadget.DESCRIPTOR)
        for name, value in {'subclass': '1', 'protocol': '1', 'report_length': '8'}.items():
            (function / name).write_text(value)
        (self.path / 'configs/c.1/hid.usb0').symlink_to(function)

    def test_stop_preserves_foreign_identity_and_binding(self):
        self.owned_fixture()
        (self.path / 'strings/0x409/serialnumber').write_text('someone-else')
        with mock.patch.object(gadget, '_remove_created') as remove:
            with self.assertRaisesRegex(RuntimeError, 'ownership'):
                gadget.stop()
            remove.assert_not_called()
        self.assertEqual((self.path / 'UDC').read_text(), 'controller')

    def test_stop_preserves_changed_descriptor_or_added_function(self):
        self.owned_fixture()
        (self.path / 'functions/hid.usb0/report_desc').write_bytes(b'changed')
        with self.assertRaises(RuntimeError):
            gadget.stop()
        (self.path / 'functions/hid.usb0/report_desc').write_bytes(gadget.DESCRIPTOR)
        (self.path / 'functions/hid.usb1').mkdir()
        with self.assertRaises(RuntimeError):
            gadget.stop()
        self.assertEqual((self.path / 'UDC').read_text(), 'controller')

    def test_stop_preserves_extra_language_strings(self):
        self.owned_fixture()
        (self.path / 'strings/0x407').mkdir()
        with self.assertRaisesRegex(RuntimeError, 'string languages'):
            gadget.stop()
        self.assertEqual((self.path / 'UDC').read_text(), 'controller')

    def test_stop_removes_only_after_ownership_check(self):
        self.owned_fixture()
        with mock.patch.object(gadget, '_remove_created') as remove:
            gadget.stop()
            remove.assert_called_once_with()

    def test_start_preserves_unrelated_gadget(self):
        (self.udc / 'controller').mkdir()
        other = self.root / 'other'
        other.mkdir()
        with mock.patch.object(gadget.subprocess, 'run'):
            with self.assertRaisesRegex(RuntimeError, 'Preserving existing gadget'):
                gadget.start()
        self.assertFalse(self.path.exists())
        self.assertTrue(other.exists())

    def test_existing_gadget_is_rechecked_on_start(self):
        self.owned_fixture()
        (self.udc / 'controller').mkdir()
        (self.path / 'functions/hid.usb0/protocol').write_text('0')
        with mock.patch.object(gadget.subprocess, 'run'):
            with self.assertRaisesRegex(RuntimeError, 'protocol'):
                gadget.start()

    def test_full_speed_is_selected_before_binding(self):
        (self.udc / 'controller').mkdir()
        (self.dev / 'hidg0').touch()
        original_mkdir = Path.mkdir
        original_glob = Path.glob
        hid_checks = 0

        def mkdir(path, *args, **kwargs):
            original_mkdir(path, *args, **kwargs)
            if path == self.path:
                for name in ('strings', 'configs', 'functions'):
                    original_mkdir(path / name)
                (path / 'max_speed').touch()
            elif path == self.path / 'configs/c.1':
                original_mkdir(path / 'strings')

        def glob(path, pattern):
            nonlocal hid_checks
            if path == self.dev:
                hid_checks += 1
                if hid_checks == 1:
                    return iter([])  # No pre-existing HID node before creation.
            return original_glob(path, pattern)

        with mock.patch.object(gadget.subprocess, 'run'), \
                mock.patch.object(Path, 'mkdir', mkdir), \
                mock.patch.object(Path, 'glob', glob), \
                mock.patch.object(gadget, 'put', wraps=gadget.put) as put, \
                contextlib.redirect_stdout(io.StringIO()):
            gadget.start()
        written = [call.args for call in put.call_args_list]
        self.assertLess(written.index((self.path / 'max_speed', 'full-speed')),
                        written.index((self.path / 'UDC', 'controller')))
        gadget.assert_owned()


if __name__ == '__main__':
    unittest.main()
