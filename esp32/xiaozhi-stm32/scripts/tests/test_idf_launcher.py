import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import unittest
from unittest import mock


source = Path(__file__).resolve().parents[1] / "build.py"
spec = importlib.util.spec_from_file_location("build_launcher_under_test", source)
build = importlib.util.module_from_spec(spec)
original_directory = os.getcwd()
try:
    spec.loader.exec_module(build)
finally:
    os.chdir(original_directory)


class IdfLauncherTests(unittest.TestCase):
    def test_sdk_path_uses_current_python_and_keeps_arguments_separate(self):
        with mock.patch.dict(os.environ, {"IDF_PATH": "sdk with spaces"}), mock.patch.object(
            build.subprocess, "run", return_value=mock.Mock(returncode=0)
        ) as run:
            build._run_idf("-D", "NAME=value with spaces", "build")
        run.assert_called_once_with(
            [sys.executable, str(Path("sdk with spaces") / "tools" / "idf.py"),
             "-D", "NAME=value with spaces", "build"], check=False
        )

    def test_preview_precedes_idf_arguments(self):
        with mock.patch.dict(os.environ, {"IDF_PATH": "sdk"}), mock.patch.object(
            build.subprocess, "run", return_value=mock.Mock(returncode=0)
        ) as run:
            build._run_idf("merge-bin", preview=True)
        run.assert_called_once_with(
            [sys.executable, str(Path("sdk") / "tools" / "idf.py"),
             "--preview", "merge-bin"], check=False
        )

    def test_no_sdk_path_preserves_path_launcher(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            build.subprocess, "run", return_value=mock.Mock(returncode=0)
        ) as run:
            build._run_idf("build")
        run.assert_called_once_with(["idf.py", "build"], check=False)

    def test_failed_process_exits_and_reports_command(self):
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"IDF_PATH": "sdk"}), mock.patch.object(
            build.subprocess, "run", return_value=mock.Mock(returncode=7)
        ), contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as failure:
            build._run_idf("build")
        self.assertEqual(failure.exception.code, 1)
        self.assertIn("idf.py", stderr.getvalue())
        self.assertIn("build failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
