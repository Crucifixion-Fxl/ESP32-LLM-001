"""Host-only regressions for relocated paths and non-destructive flash planning."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.flash_data import build_command
from tools.paths import REPOSITORY_ROOT


class FlashPlanTests(unittest.TestCase):
    def test_master_checks_every_file_before_planning_all_regions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bins').mkdir()
            for name in ('tokenizer.bin', 'bins/embed.bin', 'bins/final_norm.bin'):
                (root / name).write_bytes(b'fixture')
            command = build_command('master', 'TEST_PORT', root)
            self.assertEqual(command[command.index('write-flash')+1::2], ['0x90000', '0x150000', '0xFF0000'])
            self.assertIn('TEST_PORT', command)
            (root / 'bins/final_norm.bin').unlink()
            with self.assertRaises(FileNotFoundError):
                build_command('master', 'TEST_PORT', root)

    def test_node_requires_a_valid_physical_layer_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bins').mkdir()
            (root / 'bins/layers_20_to_23.bin').write_bytes(b'fixture')
            command = build_command('node', 'TEST_PORT', root, 'layers_20_to_23.bin')
            self.assertEqual(command[-2], '0x90000')
            for invalid in (None, 'layers_1_to_4.bin', '../layers_20_to_23.bin'):
                with self.assertRaises(ValueError):
                    build_command('node', 'TEST_PORT', root, invalid)

    def test_dry_run_never_invokes_esptool(self):
        from scripts.flash_data import main
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bins').mkdir()
            (root / 'bins/layers_0_to_3.bin').write_bytes(b'fixture')
            argv = ['flash_data.py', 'node', '--port', 'TEST_PORT', '--model-dir', directory,
                    '--layer', 'layers_0_to_3.bin', '--dry-run']
            with patch.object(sys, 'argv', argv), patch('scripts.flash_data.subprocess.run') as run:
                main()
                run.assert_not_called()


class WorkspaceTests(unittest.TestCase):
    def test_workspace_override_resolves_model_paths_independent_of_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, PYTHONPATH=str(REPOSITORY_ROOT), ESP32_LLM_WORKSPACE=directory)
            output = subprocess.check_output([sys.executable, '-c',
                'from tools.paths import MODEL_DIR, SOURCE_MODEL_DIR; print(MODEL_DIR); print(SOURCE_MODEL_DIR)'],
                cwd=directory, env=env, text=True)
            self.assertEqual(output.splitlines(), [str(Path(directory).resolve() / 'cropped_Qwen'),
                                                   str(Path(directory).resolve() / 'Qwen2-0.5B')])


if __name__ == '__main__':
    unittest.main()
