"""Native export and launcher regressions without opening GUI windows."""
import base64
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import replanv2_1 as desktop


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.webview = SimpleNamespace(FileDialog=SimpleNamespace(SAVE='save'))
        self.api = desktop.DesktopAPI(self.webview)
        self.window = Mock()
        self.api._attach(self.window)

    def test_pdf_bytes_are_saved_to_the_user_selected_file(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory) / 'checklist.pdf'
            self.window.create_file_dialog.return_value = (str(destination),)
            payload = b'%PDF-1.4\nexample\x00\xff'
            result = self.api.save_file('replan-checklist.pdf', base64.b64encode(payload).decode())
            self.assertTrue(result['saved'])
            self.assertEqual(destination.read_bytes(), payload)

    def test_cancel_saves_nothing(self):
        self.window.create_file_dialog.return_value = None
        self.assertEqual(self.api.save_file('plan.json', 'e30='), {'saved': False})

    def test_suggested_names_cannot_choose_the_destination(self):
        self.window.create_file_dialog.return_value = None
        self.api.save_file('../../plan.csv', 'e30=')
        self.assertEqual(self.window.create_file_dialog.call_args.kwargs['save_filename'], 'plan.csv')

    def test_invalid_formats_and_bad_data_never_open_a_dialog(self):
        for filename, payload in [('script.py', 'e30='), ('plan.pdf', 'not base64!')]:
            with self.assertRaises(ValueError):
                self.api.save_file(filename, payload)
        self.window.create_file_dialog.assert_not_called()

    def test_dialog_result_without_extension_gets_the_export_extension(self):
        with TemporaryDirectory() as directory:
            selected = Path(directory) / 'semester'
            self.window.create_file_dialog.return_value = str(selected)
            self.api.save_file('plan.json', 'e30=')
            self.assertEqual(selected.with_suffix('.json').read_text(), '{}')

    def test_launch_uses_persistent_storage_and_a_stable_origin(self):
        fake = SimpleNamespace(settings={}, create_window=Mock(return_value=self.window), start=Mock())
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for asset in desktop.ASSETS:
                (root / asset).touch()
            with patch.object(desktop, 'APP_ROOT', root), patch.dict('sys.modules', {'webview': fake}):
                self.assertEqual(desktop.main([]), 0)
            options = fake.start.call_args.kwargs
            self.assertFalse(options['private_mode'])
            self.assertEqual(options['http_port'], desktop.DEFAULT_PORT)
            self.assertEqual(options['storage_path'], str(root / '.replanv2-desktop'))
            self.assertEqual(fake.create_window.call_args.args[0], desktop.APP_NAME)


if __name__ == '__main__':
    unittest.main()
