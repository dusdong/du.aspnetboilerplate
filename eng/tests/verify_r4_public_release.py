#!/usr/bin/env python3
"""用隔离交接副本与真实公开样本复跑 R4 公开主包、依赖和符号入口。"""

import argparse
from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, call, patch
from zipfile import ZIP_DEFLATED, ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import r4_public_release as release
from verify import VerificationError, read_json, sha256


ENGINE = "Du.AutoMapper"
COLLECTION = "Du.AutoMapper.Collection"
INDEPENDENT = "Du.Abp"
SERILOG_SHA = "edfdc4a42b046c3c5782cba1138df4295235e29ee80d4b82b70469382aad9dbb"


def repack(data, *, changes=None, add=None, remove=()):
    changes = changes or {}
    result = BytesIO()
    with ZipFile(BytesIO(data)) as original, ZipFile(result, "w", ZIP_DEFLATED) as changed:
        for item in original.infolist():
            if item.filename not in remove:
                changed.writestr(item, changes.get(item.filename, original.read(item)))
        for name, payload in (add or {}).items():
            changed.writestr(name, payload)
    return result.getvalue()


def download_result(url, status):
    return {"url": url, "effectiveUrl": url, "httpStatus": status}


class PublicReleaseTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix="r4-public-release-tests-")
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.nuget = Mock(spec=release.NuGet)
        self.dotnet = Mock(spec=release.Dotnet)
        self.dotnet.signature.side_effect = self.signature
        self.nuget.owners.return_value = {"httpStatus": 200, "owners": ["maintainer"]}
        self.nuget.get.side_effect = self.get
        self.downloads = {}
        self.progress = self.resume()

    def resume(self):
        return release.Progress(self.manifest, release.MANIFEST_SHA256, self.handoff, self.work, self.nuget,
                                self.dotnet)

    def signature(self, package, fingerprints, directory):
        log = directory / "signature.log"
        log.write_text("隔离样本的仓库验签替身\n", encoding="utf-8")
        return {"owners": ["maintainer"], "logSha256": sha256(log)}

    def get(self, url, headers=None):
        result = self.downloads.get(url, 404)
        if isinstance(result, Exception):
            raise result
        if isinstance(result, int):
            return download_result(url, result), None
        return download_result(url, 200), result

    def frozen(self, name, kind="archive"):
        return self.handoff / self.manifest["packages"][name][kind]["path"]

    def mock_signed(self, name, **changes):
        archive = self.frozen(name).read_bytes()
        return repack(archive, add={release.SIGNATURE: b"isolated fixture"}, **changes)

    def url(self, name):
        return f"{release.GALLERY}/{name}/{self.manifest['packages'][name]['version']}"

    def observed(self, name, outcome="accepted"):
        owners = ["maintainer"] if outcome in ("accepted", "confirmed") else []
        self.progress.record("main", name, outcome, "隔离样本操作凭证", owners)

    def observed_symbols(self, outcome):
        self.progress.record("symbols", ENGINE, outcome, "隔离样本符号操作凭证", [],
                             sha256(self.frozen(ENGINE, "symbols")))

    def downloads_report(self):
        return read_json(self.work / "verified-downloads.json")["packages"]

    def test_owner_lookup_recovers_when_regional_search_nodes_have_no_match(self):
        regional = [
            "https://azuresearch-ea.nuget.org/query",
            "https://azuresearch-sea.nuget.org/query",
        ]
        index = download_result(release.NUGET_SOURCE, 200) | {
            "effectiveUrl": "https://nuget.azure.cn/v3/index.json",
        }
        service_index = {"resources": [{"@type": "SearchQueryService", "@id": url} for url in regional]}
        query = "?q=packageid%3ADu.AutoMapper&take=5&semVerLevel=2.0.0"
        search_urls = [base + query for base in [*regional, release.GLOBAL_SEARCH]]
        responses = [
            {"data": []},
            {"data": [{"id": "Du.AutoMapper.Collection", "owners": ["different-owner"]}]},
            {"data": [{"id": "DU.AUTOMAPPER", "owners": "dusdong"}]},
        ]
        nuget = release.NuGet(1)
        with patch.object(nuget, "get", side_effect=[
            (index, json.dumps(service_index).encode()),
            *((download_result(url, 200), json.dumps(body).encode()) for url, body in zip(search_urls, responses)),
        ]) as request:
            owners = nuget.owners(ENGINE)
        self.assertEqual(["dusdong"], owners["owners"])
        self.assertEqual(search_urls[-1], owners["url"])
        self.assertEqual([[], [], ["dusdong"]], [attempt["owners"] for attempt in owners["attempts"]])
        self.assertEqual([call(release.NUGET_SOURCE, metadata=True), *(call(url) for url in search_urls)],
                         request.call_args_list)

    def test_archive_reports_missing_extra_and_changed_members(self):
        original = self.frozen(ENGINE)
        with ZipFile(original) as archive:
            dll = next(file for file in archive.namelist() if file.endswith(".dll"))
        self.observed(ENGINE)
        for changes in ({"remove": ["README.md"]}, {"changes": {dll: b"different"}}):
            self.downloads[self.url(ENGINE)] = self.mock_signed(ENGINE, **changes)
            result = self.progress.check_main(ENGINE)
            self.assertEqual("failed", result["status"])
            self.assertIn("README.md" if "remove" in changes else dll, result["reason"])
            self.assertIn("downloadSha256", result)
        self.downloads[self.url(ENGINE)] = repack(original.read_bytes(),
                                                  add={release.SIGNATURE: b"fixture", "extra": b"unexpected"})
        self.assertIn('"extra": ["extra"]', self.progress.check_main(ENGINE)["reason"])
        self.assertEqual({}, self.downloads_report())

    def test_gate_blocks_pending_and_failed_engine_then_releases_collection(self):
        self.observed(ENGINE)
        self.downloads[self.url(ENGINE)] = TimeoutError("隔离样本的读取超时")
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(2, self.progress.gate(COLLECTION))
        self.assertIn(ENGINE, output.getvalue())
        self.assertIn('"status": "pending"', output.getvalue())
        self.assertIn("TimeoutError", output.getvalue())

        self.progress = self.resume()
        self.downloads[self.url(ENGINE)] = 404
        self.assertEqual(2, self.progress.gate(COLLECTION))
        with redirect_stdout(output := StringIO()):
            self.assertEqual(2, self.progress.gate("Du.Abp.AutoMapper"))
        self.assertIn(f'"{COLLECTION}": {{"version": "11.0.0", "status": "notVisible"}}', output.getvalue())
        self.assertEqual(0, self.progress.gate(INDEPENDENT))
        self.downloads[self.url(ENGINE)] = self.mock_signed(ENGINE, changes={"README.md": b"changed"})
        self.assertEqual(2, self.progress.gate(COLLECTION))
        self.assertEqual("failed", self.progress.state["packages"][ENGINE]["main"][-1]["status"])
        self.assertEqual(0, self.progress.gate(INDEPENDENT))

        self.progress = self.resume()
        self.observed_symbols("accepted")
        self.downloads[self.url(ENGINE)] = self.mock_signed(ENGINE)
        self.assertEqual(0, self.progress.gate(COLLECTION))
        summary = self.downloads_report()
        self.assertEqual({ENGINE}, summary.keys())
        row = summary[ENGINE]
        self.assertEqual("14.0.0", row["version"])
        self.assertEqual(sha256(self.frozen(ENGINE)), row["uploadSha256"])
        self.assertEqual(release.bytes_sha256(self.downloads[self.url(ENGINE)]), row["downloadSha256"])
        self.assertNotEqual(row["uploadSha256"], row["downloadSha256"])
        self.assertEqual("accepted", self.progress.observation("symbols", ENGINE)["outcome"])

        verified_history = self.progress.state["packages"][ENGINE]["main"][:]
        self.progress = self.resume()
        self.downloads[self.url(ENGINE)] = AssertionError("已确认的归档不应再次请求")
        self.assertEqual(0, self.progress.gate(COLLECTION))
        self.assertEqual(verified_history, self.progress.state["packages"][ENGINE]["main"])
        self.assertEqual(summary, self.downloads_report())

    def test_resume_rebuilds_summary_and_discards_a_changed_download(self):
        self.observed(ENGINE)
        self.downloads[self.url(ENGINE)] = self.mock_signed(ENGINE)
        verified = self.progress.check_main(ENGINE)
        self.assertEqual("verified", verified["status"])
        summary = self.downloads_report()
        self.progress.downloads.unlink()
        self.progress = self.resume()
        self.assertEqual(summary, self.downloads_report())

        downloaded = self.work / verified["evidence"] / f"{ENGINE}.14.0.0.nupkg"
        downloaded.write_bytes(b"changed retained file")
        self.downloads[self.url(ENGINE)] = 404
        self.assertEqual("pending", self.progress.check_main(ENGINE)["status"])
        self.assertEqual({}, self.downloads_report())
        self.assertEqual(verified, self.progress.state["packages"][ENGINE]["main"][0])

    def test_duplicate_requires_same_batch_owner_confirmation(self):
        self.observed(ENGINE, "duplicate")
        self.assertEqual("conflict", self.progress.check_main(ENGINE)["status"])
        self.downloads[self.url(ENGINE)] = self.mock_signed(ENGINE)
        self.assertEqual("conflict", self.progress.check_main(ENGINE)["status"])
        self.observed(ENGINE, "confirmed")
        self.nuget.owners.return_value = {"httpStatus": 200, "owners": ["another-owner"]}
        result = self.progress.check_main(ENGINE)
        self.assertEqual("conflict", result["status"])
        self.assertIn("当前所有者", result["reason"])
        self.assertEqual({}, self.downloads_report())
        self.nuget.owners.return_value = {"httpStatus": 200, "owners": ["MAINTAINER"]}
        self.assertEqual("verified", self.progress.check_main(ENGINE)["status"])
        self.assertIn(ENGINE, self.downloads_report())
        self.observed(ENGINE, "duplicate")
        self.assertNotIn(ENGINE, self.downloads_report())

    def test_uncertain_upload_requires_readback_or_documented_retry(self):
        self.observed(ENGINE, "timeout")
        self.assertEqual(2, self.progress.gate(ENGINE))
        self.observed(ENGINE, "retry")
        self.assertEqual(0, self.progress.gate(ENGINE))
        self.downloads[self.url(ENGINE)] = self.mock_signed(ENGINE)
        self.assertEqual(2, self.progress.gate(ENGINE))
        self.assertEqual("conflict", self.progress.state["packages"][ENGINE]["main"][-1]["status"])

    def engine_symbol_fixture(self):
        self.observed(ENGINE)
        self.downloads[self.url(ENGINE)] = self.mock_signed(ENGINE)
        main = self.progress.check_main(ENGINE)
        self.progress.dotnet = release.Dotnet(self.work)
        archive_path = "lib/net8.0/AutoMapper.pdb"
        with ZipFile(self.frozen(ENGINE, "symbols")) as archive:
            pdb = archive.read(archive_path)
        with ZipFile(self.frozen(ENGINE)) as archive:
            dll = self.work / "AutoMapper.dll"
            dll.write_bytes(archive.read("lib/net8.0/AutoMapper.dll"))
        debug = self.progress.dotnet.symbol(self.work, dll)
        return main, archive_path, pdb, dll, debug

    def test_symbol_is_checked_against_its_target_and_frozen_digest(self):
        main, archive_path, pdb, dll, debug = self.engine_symbol_fixture()
        url = f"{release.SYMBOLS}/automapper.pdb/{debug['guid'].lower()}FFFFFFFF/automapper.pdb"
        self.observed_symbols("accepted")
        self.assertEqual(["pending"], self.progress.check_symbols(ENGINE, main))
        self.nuget.get.assert_called_with(url, headers={"SymbolChecksum": debug["checksum"]})
        rows = self.progress.state["packages"][ENGINE]["symbols"]["lib/net8.0/AutoMapper.dll"]
        self.assertEqual(404, rows[-1]["readback"]["httpStatus"])
        self.downloads[url] = b"different portable PDB"
        self.assertEqual(["failed"], self.progress.check_symbols(ENGINE, main))
        row = self.progress.state["packages"][ENGINE]["symbols"]["lib/net8.0/AutoMapper.dll"][-1]
        self.assertEqual("net8.0", row["tfm"])
        self.assertIn(archive_path, row["reason"])
        pdb_file = self.work / "bad.pdb"
        pdb_file.write_bytes(pdb[:-1] + bytes([pdb[-1] ^ 1]))
        with self.assertRaises(VerificationError):
            self.progress.dotnet.symbol(self.work, dll, pdb_file)
        self.downloads[url] = pdb
        with patch.object(self.progress.dotnet, "symbol", side_effect=[debug, debug | {"age": 2}]):
            self.assertEqual(["failed"], self.progress.check_symbols(ENGINE, main))
        self.assertIn("PDB 调试标识复核不符", rows[-1]["reason"])
        self.assertEqual(["verified"], self.progress.check_symbols(ENGINE, main))
        history = self.progress.state["packages"][ENGINE]["symbols"]["lib/net8.0/AutoMapper.dll"][:]
        self.assertEqual(debug, history[-1]["debug"])
        self.assertEqual(200, history[-1]["readback"]["httpStatus"])
        self.assertEqual(release.bytes_sha256(pdb), history[-1]["downloadSha256"])
        readback = history[-1]["readback"]
        readback["url"] = readback["effectiveUrl"] = (
            f"{release.SYMBOLS}/AutoMapper.pdb/{debug['guid']}FFFFFFFF/AutoMapper.pdb"
        )
        self.progress.save()
        self.progress = self.resume()
        self.nuget.get.reset_mock()
        self.assertEqual(["verified"], self.progress.check_symbols(ENGINE, main))
        self.nuget.get.assert_not_called()
        self.assertEqual(history, self.progress.state["packages"][ENGINE]["symbols"]["lib/net8.0/AutoMapper.dll"])

    def test_full_verification_requires_symbol_receipt_even_with_cached_matching_pdb(self):
        _, _, pdb, _, debug = self.engine_symbol_fixture()
        url = f"{release.SYMBOLS}/automapper.pdb/{debug['guid'].lower()}FFFFFFFF/automapper.pdb"
        self.downloads[url] = pdb
        self.assertEqual(2, self.progress.verify([ENGINE], main_only=False))
        symbols = self.progress.state["packages"][ENGINE]["symbols"]
        history = symbols["lib/net8.0/AutoMapper.dll"][:]
        self.assertEqual("verified", history[0]["status"])
        self.downloads[url] = AssertionError("已确认的 PDB 无须重复请求")
        self.assertEqual(0, self.progress.verify([ENGINE], main_only=True))

        with self.assertRaisesRegex(VerificationError, "实传符号包 SHA-256"):
            self.progress.record("symbols", ENGINE, "accepted", "摘要错误的隔离凭证", [], "0" * 64)
        with self.assertRaisesRegex(VerificationError, "操作凭证引用不能为空"):
            self.progress.record("symbols", ENGINE, "confirmed", "  ", [], sha256(self.frozen(ENGINE, "symbols")))
        self.observed_symbols("accepted")
        self.assertEqual(0, self.progress.verify([ENGINE], main_only=False))
        receipt = self.progress.observation("symbols", ENGINE)
        self.assertEqual(sha256(self.frozen(ENGINE, "symbols")), receipt["uploadSha256"])
        with patch.dict(receipt, {"uploadSha256": "0" * 64}):
            self.assertEqual(1, self.progress.verify([ENGINE], main_only=False))

        self.observed_symbols("duplicate")
        self.progress = self.resume()
        self.assertEqual(1, self.progress.verify([ENGINE], main_only=False))
        self.observed_symbols("failed")
        self.progress = self.resume()
        self.assertEqual(1, self.progress.verify([ENGINE], main_only=False))
        self.assertEqual(0, self.progress.gate(COLLECTION))
        self.observed_symbols("confirmed")
        self.assertEqual(0, self.progress.verify([ENGINE], main_only=False))
        self.assertEqual(history, self.progress.state["packages"][ENGINE]["symbols"]["lib/net8.0/AutoMapper.dll"])
        self.assertEqual(["accepted", "duplicate", "failed", "confirmed"],
                         [row["outcome"] for row in self.progress.state["external"][f"symbols/{ENGINE}"]])

    def test_all_frozen_targets_have_nuget_compatible_portable_debug_identity(self):
        tool = release.Dotnet(self.work)
        seen = []
        for name, row in self.manifest["packages"].items():
            with ZipFile(self.frozen(name)) as archive, ZipFile(self.frozen(name, "symbols")) as symbols:
                for tfm in row["targets"]:
                    assets = [asset for asset in archive.namelist()
                              if asset.startswith(f"lib/{tfm}/") and asset.endswith(".dll")]
                    self.assertEqual(1, len(assets))
                    asset = assets[0]
                    directory = self.work / name / tfm
                    directory.mkdir(parents=True)
                    dll = directory / Path(asset).name
                    pdb = dll.with_suffix(".pdb")
                    dll.write_bytes(archive.read(asset))
                    pdb.write_bytes(symbols.read(asset.removesuffix(".dll") + ".pdb"))
                    marker = tool.symbol(directory, dll)
                    self.assertEqual(pdb.name, marker["name"])
                    self.assertEqual(marker, tool.symbol(directory, dll, pdb))
                    seen.append((name, tfm))
        self.assertEqual(18, len(seen))


class RealProtocolTests(unittest.TestCase):
    def test_real_nuget_repository_signature_and_public_portable_pdb(self):
        work = self.evidence
        work.mkdir(parents=True)
        handoff = work / "sample-inputs"
        handoff.mkdir()
        nuget = release.NuGet(20)
        tool = release.Dotnet(work)
        url = f"{release.GALLERY}/Serilog/4.2.0"
        response, signed = nuget.get(url)
        self.assertEqual(200, response["httpStatus"])
        self.assertEqual(SERILOG_SHA, release.bytes_sha256(signed))
        archive_path = handoff / "Serilog.4.2.0.nupkg"
        archive_path.write_bytes(repack(signed, remove=(release.SIGNATURE,)))
        self.assertNotEqual(SERILOG_SHA, sha256(archive_path))
        dll = work / "Serilog.dll"
        with ZipFile(archive_path) as archive:
            dll.write_bytes(archive.read("lib/net8.0/Serilog.dll"))
        debug = tool.symbol(work, dll)
        symbol_name = debug["name"]
        pdb_key = symbol_name.lower()
        response, symbol = nuget.get(f"{release.SYMBOLS}/{pdb_key}/{debug['guid'].lower()}FFFFFFFF/{pdb_key}",
                                     headers={"SymbolChecksum": debug["checksum"]})
        self.assertEqual(200, response["httpStatus"])
        self.assertNotIn("?", response["effectiveUrl"])
        symbols = handoff / "Serilog.4.2.0.snupkg"
        with ZipFile(symbols, "w") as archive:
            archive.writestr(f"lib/net8.0/{symbol_name}", symbol)
        release_row = {
            "archive": {"path": archive_path.name, "sha256": sha256(archive_path)},
            "symbols": {"path": symbols.name, "sha256": sha256(symbols)},
            "version": "4.2.0", "targets": {"net8.0": {}},
        }
        manifest = {"release": {"repository": "隔离公开协议样本"}, "packages": {"Serilog": release_row}}
        progress = release.Progress(manifest, "serilog-protocol-sample", handoff, work, nuget, tool)
        self.assertEqual("conflict", progress.check_main("Serilog")["status"])
        progress.record("main", "Serilog", "confirmed", "已公开协议样本，仅测试证据分离", ["serilog"])
        main = progress.check_main("Serilog")
        self.assertEqual("verified", main["status"])
        self.assertEqual("2024-12-06T04:13:15+00:00", main["signature"]["timestampUtc"])
        self.assertEqual(SERILOG_SHA, main["downloadSha256"])
        self.assertEqual(2, progress.verify(["Serilog"], main_only=False))
        target = progress.state["packages"]["Serilog"]["symbols"]["lib/net8.0/Serilog.dll"][-1]
        self.assertEqual("verified", target["status"])
        self.assertIsNone(progress.observation("symbols", "Serilog"))
        self.assertEqual(SERILOG_SHA, read_json(work / "verified-downloads.json")["packages"]["Serilog"]["downloadSha256"])

        damaged = work / "invalid-signed.nupkg"
        with ZipFile(archive_path) as original:
            changed = next(name for name in original.namelist() if name.endswith(".nuspec"))
        damaged.write_bytes(repack(signed, changes={changed: b"invalid content"}))
        invalid = work / "bad-signature"
        invalid.mkdir()
        with self.assertRaises(VerificationError):
            tool.signature(damaged, nuget.certificates(work), invalid)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--online-evidence", type=Path, help="新目录，保存独立的真实公开协议样本证据")
    args, unittest_args = parser.parse_known_args()
    PublicReleaseTests.handoff = args.handoff.resolve()
    PublicReleaseTests.manifest = read_json(args.manifest)
    checks = [PublicReleaseTests.__name__]
    if args.online_evidence:
        RealProtocolTests.evidence = args.online_evidence.resolve()
        checks.append(RealProtocolTests.__name__)
    unittest.main(argv=[sys.argv[0], *unittest_args], defaultTest=checks)
