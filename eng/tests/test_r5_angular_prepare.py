"""独立冻结 Angular 入口的清单拒绝和构建差异诊断回归。"""

import hashlib
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3_template_runtime import inventory
from r3_web_host import write_json
from r5_angular_prepare import BROWSER, INDEX_SHA256, MANIFEST, production_identity
from r5_angular_role_edit import ANGULAR_INVENTORY, ANGULAR_MANIFEST, EDIT_CHUNK, EDIT_SHA256, main as role_main
from verify import ROOT


class AngularPrepareTests(unittest.TestCase):
    def test_role_entry_resolves_angular_source_and_keeps_historical_default(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            argv = [
                "r5_angular_role_edit.py", "--output", str(root / "report"), "--prepared", str(root / "prepared"),
                "--report-sha256", "unused", "--chrome", "unused", "--r4-port", "52361",
                "--r4-frontend-port", "52362", "--r5-port", "52371", "--r5-frontend-port", "52372",
            ]
            relocated = root / "relocated"
            historical = ROOT / ".git/r3-template-runtime/revision-1/runs/r3-template-runtime-89igcw5r"
            for extra, expected in (([], historical), (["--angular-source", str(relocated)], relocated)):
                with self.subTest(source=expected), patch.object(sys, "argv", argv + extra), \
                        patch("r5_angular_role_edit.AngularRun") as run:
                    run.return_value.execute.return_value = 0
                    self.assertEqual(role_main(), 0)
                    self.assertEqual(run.call_args.args[0].angular_source, expected.resolve())

    def test_verify_rejects_wrong_manifest_before_reading_static_files(self):
        with TemporaryDirectory() as directory:
            source = Path(directory)
            manifest = source / MANIFEST
            original = b'{"sha256":"altered","files":{}}\n'
            manifest.write_bytes(original)
            result = subprocess.run(
                [sys.executable, "-B", "-S", ROOT / "eng/r5_angular_prepare.py",
                 "verify", "--angular-source", source],
                cwd=source, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("冻结 Angular 清单文件摘要不符", result.stderr)
            self.assertEqual(manifest.read_bytes(), original)
            self.assertFalse((source / BROWSER).exists())

    def test_identity_reports_changed_index_and_hashes_exact_inline_css_bytes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / MANIFEST
            manifest.write_bytes(b"new manifest\n")
            css = b"\r\n@font-face{font-family:'Source Sans Pro'}\n"
            html = b"<style>body{margin:0}</style><style>" + css + b"</style>\n"
            (root / "index.html").write_bytes(html)
            index_hash = hashlib.sha256(html).hexdigest()

            identity = production_identity({"files": {"index.html": index_hash}, "sha256": "new"}, manifest, root)

            self.assertEqual(identity["index"]["actual"], index_hash)
            self.assertNotEqual(identity["index"]["expected"], index_hash)
            self.assertEqual(identity["manifest"]["actual"], hashlib.sha256(manifest.read_bytes()).hexdigest())
            self.assertEqual(identity["inventory"]["actual"], "new")
            self.assertEqual(identity["font"]["actual"], hashlib.sha256(css).hexdigest())
            self.assertEqual(identity["font"]["bytes"], len(css))
            self.assertEqual(identity["font"]["fontFaces"], 1)

    def test_font_references_without_target_font_face_report_missing(self):
        for css in (
            b'@font-face{font-family:"Font Awesome"}body{font-family:"Source Sans Pro"}',
            b'@font-face{font-family:"Other";src:local("Source Sans Pro")}',
        ):
            with self.subTest(css=css), TemporaryDirectory() as directory:
                root = Path(directory)
                html = b"<style>" + css + b"</style>"
                (root / "index.html").write_bytes(html)
                manifest = root / MANIFEST
                manifest.write_bytes(b"manifest\n")

                identity = production_identity(
                    {"files": {"index.html": hashlib.sha256(html).hexdigest()}, "sha256": "new"}, manifest, root,
                )

                self.assertIsNone(identity["font"]["actual"])
                self.assertEqual(identity["font"]["bytes"], 0)
                self.assertEqual(identity["font"]["fontFaces"], 0)

    def test_font_family_comments_end_at_the_first_closing_delimiter(self):
        for family, matches in (
            (b"/*one*/ Other /*two*/ Source Sans Pro", False),
            (b"Source Sans Pro /*one*/ Variable /*two*/", False),
            (b"/*one*/ Source /*two*/ Sans Pro /*tail****/", True),
        ):
            with self.subTest(family=family), TemporaryDirectory() as directory:
                root = Path(directory)
                css = b"@font-face{font-family: " + family + b"}"
                html = b"<style>" + css + b"</style>"
                (root / "index.html").write_bytes(html)
                manifest = root / MANIFEST
                manifest.write_bytes(b"manifest\n")

                identity = production_identity(
                    {"files": {"index.html": hashlib.sha256(html).hexdigest()}, "sha256": "new"}, manifest, root,
                )

                self.assertEqual(identity["font"]["actual"], hashlib.sha256(css).hexdigest() if matches else None)
                self.assertEqual(identity["font"]["bytes"], len(css) if matches else 0)
                self.assertEqual(identity["font"]["fontFaces"], 1 if matches else 0)

    def test_font_identity_hashes_trailing_space_and_counts_only_rules(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            css = (b'@font-face{src:local("Other; font-family: Source Sans Pro"); font-family: Source Sans Pro;}'
                   b'@font-face{font-family:"Other"}'
                   b'/* @font-face{font-family:"Ignored"} */'
                   b'div::after{content:"@font-face{font-family:Ignored}"} ')
            html = b"<style>" + css + b"</style>"
            (root / "index.html").write_bytes(html)
            manifest = root / MANIFEST
            manifest.write_bytes(b"manifest\n")

            identity = production_identity(
                {"files": {"index.html": hashlib.sha256(html).hexdigest()}, "sha256": "new"}, manifest, root,
            )

            self.assertEqual(identity["font"]["actual"], hashlib.sha256(css).hexdigest())
            self.assertNotEqual(identity["font"]["actual"], hashlib.sha256(css[:-1]).hexdigest())
            self.assertEqual(identity["font"]["bytes"], len(css))
            self.assertEqual(identity["font"]["fontFaces"], 2)

    def test_invalid_utf8_index_preserves_both_manifest_digests_and_file_identities(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            browser = root / BROWSER
            browser.mkdir(parents=True)
            html = b"<html>changed:\xff</html>"
            edit = b"edit chunk"
            (browser / "index.html").write_bytes(html)
            (browser / EDIT_CHUNK).write_bytes(edit)
            files = inventory(browser, include_app_data=True)
            manifest = root / MANIFEST
            write_json(manifest, files)

            identity = production_identity(files, manifest, browser)

            self.assertEqual(identity["manifest"], {
                "expected": ANGULAR_MANIFEST, "actual": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            })
            self.assertEqual(identity["inventory"], {"expected": ANGULAR_INVENTORY, "actual": files["sha256"]})
            self.assertEqual(identity["index"], {"expected": INDEX_SHA256, "actual": hashlib.sha256(html).hexdigest()})
            self.assertEqual(identity["editChunk"], {
                "path": EDIT_CHUNK, "expected": EDIT_SHA256, "actual": hashlib.sha256(edit).hexdigest(),
            })
            self.assertIsNone(identity["font"]["actual"])
            self.assertEqual(identity["font"]["bytes"], 0)
            self.assertEqual(identity["font"]["fontFaces"], 0)
            self.assertNotIn("readError", identity["font"])

    def test_index_read_failure_preserves_error_and_file_identity(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / MANIFEST
            manifest.write_bytes(b"manifest\n")

            identity = production_identity(
                {"files": {"index.html": "known index digest"}, "sha256": "new"}, manifest, root,
            )

            self.assertIn("index.html", identity["font"]["readError"])
            self.assertIsNone(identity["font"]["actual"])
            self.assertEqual(identity["font"]["bytes"], 0)
            self.assertEqual(identity["font"]["fontFaces"], 0)
            self.assertEqual(identity["index"], {"expected": INDEX_SHA256, "actual": "known index digest"})


if __name__ == "__main__":
    unittest.main()
