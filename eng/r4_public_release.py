#!/usr/bin/env python3
"""匿名回读 R4 公开主包和符号，保留逐项进度并核对上传依赖。"""

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from r2_packages import NUGET_SOURCE
from r3_leaf_packages import bytes_sha256, checked_file
from r4_release_manifest import RELEASE
from verify import ROOT, VerificationError, read_json, require, sha256


MANIFEST_SHA256 = "cfe2a70f27c662edcf22424d202cbf3c6116c4510263146705bb0f721c7c670a"
SIGNATURE = ".signature.p7s"
SHA256_OID = "2.16.840.1.101.3.4.2.1"
SYMBOLS = "https://symbols.nuget.org/download/symbols"
GALLERY = "https://www.nuget.org/api/v2/package"
GLOBAL_SEARCH = "https://azuresearch-usnc.nuget.org/query"
INSPECTOR = ROOT / "eng/r4-inspection"
CONFIG = "<configuration><packageSources><clear /></packageSources></configuration>"
HEX_SHA256 = re.compile(r"[a-fA-F0-9]{64}")


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, record):
    pending = path.with_suffix(".tmp")
    pending.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    pending.replace(path)


class NuGetRedirect(HTTPRedirectHandler):
    def __init__(self, metadata=False):
        self.metadata = metadata

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        host = target.hostname or ""
        symbol_blob = urlsplit(req.full_url).hostname == "symbols.nuget.org" and re.fullmatch(
            r"[a-z0-9]+vsblobprod[a-z0-9]+\.blob\.core\.windows\.net", host)
        require(target.scheme == "https" and
                (host.endswith(".nuget.org") or (self.metadata and host == "nuget.azure.cn") or symbol_blob),
                f"NuGet 匿名请求重定向到未授权的来源：{target.scheme}://{host}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def public_url(url):
    # 符号服务可能返回带短时访问参数的对象存储 URL。
    return urlsplit(url)._replace(query="", fragment="").geturl()


class NuGet:
    def __init__(self, timeout):
        self.timeout = timeout
        self.public = build_opener(NuGetRedirect())
        self.metadata = build_opener(NuGetRedirect(metadata=True))
        self.resources = None
        self.fingerprints = None

    def get(self, url, headers=None, metadata=False):
        client = self.metadata if metadata else self.public
        try:
            response = client.open(Request(url, headers=headers or {}), timeout=self.timeout)
        except HTTPError as error:
            with error:
                return {"url": url, "effectiveUrl": public_url(error.geturl()), "httpStatus": error.code,
                        "retryAfter": error.headers.get("Retry-After")}, None
        with response:
            return {"url": url, "effectiveUrl": public_url(response.geturl()),
                    "httpStatus": response.status}, response.read()

    def index(self):
        if self.resources is None:
            source, payload = self.get(NUGET_SOURCE, metadata=True)
            require(source["httpStatus"] == 200, f"服务索引不可读：{source}")
            resources = {}
            for row in json.loads(payload)["resources"]:
                resources.setdefault(row["@type"], []).append(row["@id"])
            self.resources = source, resources
        return self.resources

    def certificates(self, work):
        if self.fingerprints is None:
            source, resources = self.index()
            url, = set(resources["RepositorySignatures/5.0.0"])
            require(url == "https://api.nuget.org/v3-index/repository-signatures/5.0.0/index.json",
                    f"仓库签名索引来源意外：{url}")
            readback, payload = self.get(url, metadata=True)
            require(readback["httpStatus"] == 200, f"仓库签名索引不可读：{readback}")
            index = json.loads(payload)
            require(index["allRepositorySigned"] is True, "nuget.org 未声明覆盖全部主包的仓库签名")
            fingerprints = {row["fingerprints"][SHA256_OID].upper() for row in index["signingCertificates"]}
            require(fingerprints and all(HEX_SHA256.fullmatch(value) for value in fingerprints), "签名指纹索引无效")
            write_json(work / "repository-signatures.json",
                       {"serviceIndex": source, "readback": readback, "index": index})
            self.fingerprints = fingerprints
        return self.fingerprints

    def owners(self, name):
        source, resources = self.index()
        endpoints = resources["SearchQueryService"]
        if urlsplit(source["effectiveUrl"]).hostname == "nuget.azure.cn":
            # 地区镜像可能尚未索引新发布。此地址是 nuget.org 全球服务索引公布的主搜索节点。
            endpoints = [*endpoints, GLOBAL_SEARCH]
        query = urlencode({"q": "packageid:" + name, "take": 5, "semVerLevel": "2.0.0"})
        attempts = []
        for base in dict.fromkeys(endpoints):
            endpoint = urlsplit(base)
            require(endpoint.scheme == "https" and (endpoint.hostname or "").endswith(".nuget.org"),
                    f"包所有者查询来源意外：{base}")
            result, data = self.get(f"{base}?{query}")
            require(result["httpStatus"] == 200, f"所有者查询失败：{result}")
            matches = [row for row in json.loads(data)["data"] if row["id"].casefold() == name.casefold()]
            owners = matches[0].get("owners", []) if matches else []
            if isinstance(owners, str):
                owners = [owners]
            attempts.append(result | {"owners": owners})
            if owners:
                break
        return attempts[-1] | {"attempts": attempts}


def member_digests(path):
    with ZipFile(path) as archive:
        files = [entry.filename for entry in archive.infolist() if not entry.is_dir()]
        require(len(files) == len({file.casefold() for file in files}), f"{path.name} 含重复文件")
        return {file: bytes_sha256(archive.read(file)) for file in sorted(files)}


def compare_packages(frozen, public):
    original = member_digests(frozen)
    downloaded = member_digests(public)
    require(SIGNATURE not in original, f"冻结主包已有 {SIGNATURE}")
    require(downloaded.pop(SIGNATURE, None), f"公开主包缺少 {SIGNATURE}")
    changes = {
        "missing": sorted(original.keys() - downloaded.keys()),
        "extra": sorted(downloaded.keys() - original.keys()),
        "changed": {file: {"expected": original[file], "actual": downloaded[file]}
                    for file in original.keys() & downloaded.keys() if original[file] != downloaded[file]},
    }
    require(not any(changes.values()), f"归档逐文件不符：{json.dumps(changes, ensure_ascii=False, sort_keys=True)}")
    return original


def signature_report(output, fingerprints):
    # 固定 SDK 的英文 CLI 使用 .NET 固定区域性和 UTC 输出时间。
    require(re.findall(r"^Signature type: (.*)$", output, re.M) == ["Repository"], "预期唯一仓库主签名")
    require(re.findall(r"^Service index: (.*)$", output, re.M) == [NUGET_SOURCE], "仓库签名服务索引不符")
    hashes = re.findall(r"^  SHA256 hash: ([A-F0-9]{64})$", output, re.M)
    times = re.findall(r"^Timestamp: (.+)$", output, re.M)
    owners = re.findall(r"^Owners: (.+)$", output, re.M)
    chains = re.split(r"^Timestamp: .+$", output, flags=re.M)
    require(len(hashes) == 2 and hashes[0] in fingerprints and len(times) == 1 and len(owners) == 1 and
            all(re.search(r"^trace:\s+SHA256 hash: [A-F0-9]{64}$", part, re.M) for part in chains),
            "仓库指纹、签名证书链、时间戳证书链或所有者证据不完整")
    require(not re.search(r"^\s*(warn|error)\s*:", output, re.M | re.I), "签名或时间戳验证有警告或错误")
    time = datetime.strptime(times[0], "%m/%d/%Y %H:%M:%S").replace(tzinfo=timezone.utc)
    return {"repository": NUGET_SOURCE, "certificateSha256": hashes[0].lower(),
            "timestampCertificateSha256": hashes[1].lower(), "timestampUtc": time.isoformat(),
            "owners": [owner.strip() for owner in owners[0].split(",")]}


class Dotnet:
    def __init__(self, work):
        self.work = work
        self.home = work / "inspector"
        self.tool = self.home / "bin/Release/net10.0/InspectDll.dll"
        self.home.mkdir(exist_ok=True)
        for file in ("global.json", "InspectDll.csproj", "Program.cs"):
            shutil.copyfile(INSPECTOR / file, self.home / file)
        (self.home / "NuGet.Config").write_text(CONFIG, encoding="utf-8")
        self.built = False

    def run(self, args, log, invariant=False):
        env = os.environ | {"DOTNET_NOLOGO": "1", "TZ": "UTC"}
        if invariant:
            env["DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"] = "1"
            env.pop("DOTNET_CLI_UI_LANGUAGE", None)
            env.pop("VSLANG", None)
        else:
            env["DOTNET_CLI_UI_LANGUAGE"] = "en-US"
        result = subprocess.run(["dotnet", *map(str, args)], cwd=self.home, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", timeout=120)
        log.write_text(result.stdout + f"\n退出码 {result.returncode}\n", encoding="utf-8")
        require(result.returncode == 0, f".NET 核验退出 {result.returncode}，证据 {log}")
        return result.stdout

    def signature(self, package, fingerprints, directory):
        config = ET.fromstring(CONFIG)
        signer = ET.SubElement(ET.SubElement(config, "trustedSigners"), "repository",
                               name="nuget.org", serviceIndex=NUGET_SOURCE)
        for fingerprint in sorted(fingerprints):
            ET.SubElement(signer, "certificate", fingerprint=fingerprint,
                          hashAlgorithm="SHA256", allowUntrustedRoot="false")
        config_path = directory / "NuGet.Config"
        ET.ElementTree(config).write(config_path, encoding="utf-8")
        log = directory / "signature.log"
        output = self.run(["nuget", "verify", package, "--verbosity", "detailed", "--configfile", config_path],
                          log, invariant=True)
        return signature_report(output, fingerprints) | {"logSha256": sha256(log)}

    def symbol(self, directory, dll, pdb=None):
        if not self.built:
            self.run(["build", "InspectDll.csproj", "-c", "Release", "--disable-build-servers"],
                     self.work / "inspector-build.log")
            self.built = True
        args = [self.tool, "--symbol", dll]
        if pdb is not None:
            args.append(pdb)
        return json.loads(self.run(args, directory / ("pdb.log" if pdb else "codeview.log")))


def pending(record, observed):
    status = record["httpStatus"]
    if status == 404:
        return "pending" if observed else "notVisible"
    if status in (408, 429) or status >= 500:
        return "pending"
    return "failed"


def normalized_owners(owners):
    return {owner.casefold() for owner in owners}


class Progress:
    def __init__(self, manifest, manifest_sha, handoff, work, nuget, dotnet):
        self.manifest = manifest
        self.handoff = handoff
        self.work = work
        self.nuget = nuget
        self.dotnet = dotnet
        self.path = work / "progress.json"
        self.downloads = work / "verified-downloads.json"
        self.state = read_json(self.path) if self.path.exists() else {
            "schemaVersion": 1, "nugetSource": NUGET_SOURCE, "manifestSha256": manifest_sha,
            "release": manifest["release"], "external": {}, "packages": {},
        }
        require(self.state["manifestSha256"] == manifest_sha, "进度记录与指定清单 SHA-256 不一致")
        if self.path.exists() and not self.downloads.exists():
            self.save()

    def save(self):
        downloads = {}
        for name, row in self.state["packages"].items():
            last = row.get("main", [None])[-1]
            if self.reusable_main(name, last, self.observation("main", name)):
                downloads[name] = {key: last[key] for key in ("version", "uploadSha256", "downloadSha256")}
        # 写入中断时允许摘要暂缺，避免消费者读到已失效的旧摘要。
        self.downloads.unlink(missing_ok=True)
        write_json(self.path, self.state)
        write_json(self.downloads, {
            "schemaVersion": 1, "manifestSha256": self.state["manifestSha256"],
            "nugetSource": NUGET_SOURCE, "packages": downloads,
        })

    def observation(self, kind, name):
        key = f"{kind}/{name}" if name else kind
        return self.state["external"].get(key, [None])[-1]

    def reusable_main(self, name, record, observation):
        if not record or record["status"] != "verified" or record["observation"] != observation:
            return False
        path = self.work / record["evidence"]
        files = {
            path / f"{name}.{record['version']}.nupkg": record["downloadSha256"],
            path / "signature.log": record["signature"]["logSha256"],
            path / "members.json": record["memberListSha256"],
        }
        return all(file.is_file() and sha256(file) == digest for file, digest in files.items())

    def record(self, kind, name, outcome, reference, owners, upload_sha=None):
        require(bool(name) == (kind in ("main", "symbols")), f"{kind} 的包 ID 参数不适用或缺失")
        require(reference.strip(), "操作凭证引用不能为空")
        key = f"{kind}/{name}" if name else kind
        entry = {"time": timestamp(), "outcome": outcome, "evidence": reference}
        if name:
            row = self.manifest["packages"][name]
            entry |= {"version": row["version"], "uploadSha256": row["archive" if kind == "main" else kind]["sha256"]}
        if kind == "symbols" and outcome in ("accepted", "confirmed"):
            require(upload_sha and upload_sha.lower() == entry["uploadSha256"],
                    f"{name}/{entry['version']}/symbols：实传符号包 SHA-256 须与清单 {entry['uploadSha256']} 一致")
        if kind == "main" and outcome in ("accepted", "confirmed"):
            require(owners, "登记主包受理或归属确认需要已核对的 NuGet 所有者")
            entry["owners"] = owners
        history = self.state["external"].setdefault(key, [])
        if not history or {k: v for k, v in history[-1].items() if k != "time"} != {
            k: v for k, v in entry.items() if k != "time"
        }:
            history.append(entry)
            self.save()

    def check_main(self, name):
        row = self.manifest["packages"][name]
        version = row["version"]
        label = f"{name}/{version}"
        observation = self.observation("main", name)
        history = self.state["packages"].setdefault(name, {}).setdefault("main", [])
        previous = history[-1] if history else None
        directory = self.work / "main" / name / f"{len(history) + 1:04d}"
        record = {"time": timestamp(), "version": version, "uploadSha256": row["archive"]["sha256"],
                  "observation": observation, "evidence": str(directory.relative_to(self.work))}
        try:
            frozen = checked_file(self.handoff, row["archive"]["path"], record["uploadSha256"])
            if self.reusable_main(name, previous, observation):
                return previous
            directory.mkdir(parents=True, exist_ok=True)
            result, data = self.nuget.get(f"{GALLERY}/{name}/{version}")
            record["readback"] = result
            if result["httpStatus"] != 200:
                awaiting = observation and observation["outcome"] != "retry"
                record["status"] = pending(result, awaiting)
                if observation and observation["outcome"] == "duplicate" and result["httpStatus"] == 404:
                    record["status"] = "conflict"
            else:
                package = directory / f"{name}.{version}.nupkg"
                package.write_bytes(data)
                record["downloadSha256"] = sha256(package)
                record["signature"] = self.dotnet.signature(package, self.nuget.certificates(self.work), directory)
                members = directory / "members.json"
                write_json(members, compare_packages(frozen, package))
                record["memberListSha256"] = sha256(members)
                record["owners"] = self.nuget.owners(name)
                signed = normalized_owners(record["signature"]["owners"])
                current = normalized_owners(record["owners"]["owners"])
                expected = normalized_owners(observation.get("owners", [])) if observation else set()
                if not current:
                    record.update(status="pending", reason="当前所有者尚未被公开索引返回")
                elif not expected or signed != expected or current != expected:
                    record.update(status="conflict", reason="发行归属记录、仓库签名内所有者和当前所有者须一致")
                else:
                    record["status"] = "verified"
        except (TimeoutError, URLError, subprocess.TimeoutExpired) as error:
            record.update(status="pending", reason=f"{type(error).__name__}: {error}")
        except (BadZipFile, KeyError, OSError, ValueError, VerificationError) as error:
            record.update(status="failed", reason=str(error))
        history.append(record)
        self.save()
        print(f"{label}/main {record['status']} {record.get('reason', '')}".rstrip())
        return record

    def symbol_upload_status(self, name):
        row = self.manifest["packages"][name]
        observation = self.observation("symbols", name)
        outcome = observation["outcome"] if observation else "unrecorded"
        if outcome in ("accepted", "confirmed"):
            status = "verified" if (
                observation.get("version") == row["version"]
                and observation.get("uploadSha256") == row["symbols"]["sha256"]
                and observation.get("evidence", "").strip()
            ) else "failed"
        elif outcome == "duplicate":
            status = "conflict"
        else:
            status = "failed" if outcome == "failed" else "pending"
        print(f"{name}/{row['version']}/symbolUpload {status} ({outcome})")
        return status

    def check_symbols(self, name, main):
        row = self.manifest["packages"][name]
        version = row["version"]
        if main["status"] != "verified":
            return [main["status"]]
        frozen = checked_file(self.handoff, row["symbols"]["path"], row["symbols"]["sha256"])
        public = self.work / main["evidence"] / f"{name}.{version}.nupkg"
        rows = self.state["packages"][name].setdefault("symbols", {})
        statuses = []
        with ZipFile(frozen) as symbols, ZipFile(public) as package:
            targets = {(tfm, asset) for tfm in row["targets"] for asset in package.namelist()
                       if re.fullmatch(rf"lib/{re.escape(tfm)}/[^/]+\.dll", asset)}
            require({tfm for tfm, _ in targets} == row["targets"].keys(),
                    f"{name}/{version} 的公开主包缺少登记 TFM 的 DLL")
            for tfm, asset in sorted(targets):
                history = rows.setdefault(asset, [])
                statuses.append(self.check_symbol(name, version, tfm, asset, history, main,
                                                  row["symbols"]["sha256"], package, symbols))
        return statuses

    def check_symbol(self, name, version, tfm, asset, history, main, frozen_sha, package, symbols):
        dll_name = Path(asset).name
        symbol_asset = asset.removesuffix(".dll") + ".pdb"
        directory = self.work / "symbols" / name / tfm / dll_name / f"{len(history) + 1:04d}"
        if history:
            previous = history[-1]
            previous_frozen_sha = previous.get("frozenSymbolArchiveSha256", previous.get("uploadSha256"))
            if (previous["status"] == "verified" and previous["mainSha256"] == main["downloadSha256"]
                    and previous_frozen_sha == frozen_sha):
                pdb = self.work / previous["evidence"] / previous["debug"]["name"]
                if pdb.is_file() and sha256(pdb) == previous["downloadSha256"]:
                    return "verified"
        directory.mkdir(parents=True, exist_ok=True)
        record = {"time": timestamp(), "version": version, "tfm": tfm, "asset": asset,
                  "mainSha256": main["downloadSha256"], "frozenSymbolArchiveSha256": frozen_sha,
                  "evidence": str(directory.relative_to(self.work))}
        try:
            dll = directory / dll_name
            dll.write_bytes(package.read(asset))
            record["dllSha256"] = sha256(dll)
            expected = bytes_sha256(symbols.read(symbol_asset))
            record["frozenPdbSha256"] = expected
            debug = self.dotnet.symbol(directory, dll)
            pdb_name = debug["name"]
            require(pdb_name == Path(symbol_asset).name, f"CodeView 符号文件名不符：{pdb_name}")
            record["debug"] = debug
            # 官方客户端使用小写文件名和 GUID，Portable PDB 的键固定以 FFFFFFFF 结尾。
            pdb_key = quote(pdb_name.lower())
            readback, data = self.nuget.get(f"{SYMBOLS}/{pdb_key}/{debug['guid'].lower()}FFFFFFFF/{pdb_key}",
                                           headers={"SymbolChecksum": debug["checksum"]})
            record["readback"] = readback
            if readback["httpStatus"] != 200:
                record["status"] = pending(readback, True)
            else:
                pdb = directory / pdb_name
                pdb.write_bytes(data)
                record["downloadSha256"] = sha256(pdb)
                require(record["downloadSha256"] == expected,
                        f"{symbol_asset} SHA-256 不符，预期 {expected}，实际 {record['downloadSha256']}")
                require(debug == self.dotnet.symbol(directory, dll, pdb), "PDB 调试标识复核不符")
                record["status"] = "verified"
        except (TimeoutError, URLError, subprocess.TimeoutExpired) as error:
            record.update(status="pending", reason=f"{type(error).__name__}: {error}")
        except (BadZipFile, KeyError, OSError, ValueError, VerificationError) as error:
            record.update(status="failed", reason=str(error))
        history.append(record)
        self.save()
        print(f"{name}/{version}/{asset} {record['status']} {record.get('reason', '')}".rstrip())
        return record["status"]

    def verify(self, names, main_only):
        statuses = []
        for name in dict.fromkeys(names):
            main = self.check_main(name)
            statuses.append(main["status"])
            if not main_only:
                statuses.append(self.symbol_upload_status(name))
                if main["status"] == "verified":
                    statuses.extend(self.check_symbols(name, main))
        if any(value in ("failed", "conflict") for value in statuses):
            return 1
        return 0 if all(value == "verified" for value in statuses) else 2

    def gate(self, name):
        blocked = {}
        for dependency, version in self.manifest["packages"][name]["directInternalDependencies"].items():
            status = self.check_main(dependency)["status"]
            if status != "verified":
                blocked[dependency] = {"version": version, "status": status}
        own = self.check_main(name)["status"]
        observation = self.observation("main", name)
        available = own == "notVisible" and (observation is None or observation["outcome"] == "retry")
        result = {"package": name, "main": own, "blockedBy": blocked, "ready": available and not blocked}
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["ready"] else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=15, help="单次 HTTP 请求超时秒数")
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify", help="匿名回读指定包或全批")
    verify.add_argument("--package", action="append")
    verify.add_argument("--main-only", action="store_true")
    gate = commands.add_parser("gate", help="读取指定主包及其直接内部依赖，判断是否可上传主包")
    gate.add_argument("--package", required=True)
    record = commands.add_parser("record", help="登记既有外部操作的脱敏凭证，独立于读回核验")
    record.add_argument("--kind", choices=("tag", "main", "symbols", "release"), required=True)
    record.add_argument("--package")
    record.add_argument("--outcome", choices=("accepted", "timeout", "duplicate", "confirmed", "failed", "retry"),
                        required=True)
    record.add_argument("--evidence", required=True, help="已核对的外部操作及归属凭证位置")
    record.add_argument("--owner", action="append")
    record.add_argument("--upload-sha256", help="受理或确认符号包时，提供实传符号归档的 SHA-256")
    args = parser.parse_args()
    try:
        require(1 <= args.timeout <= 60, "HTTP 请求超时须为 1 至 60 秒")
        digest = sha256(args.manifest)
        require(digest == MANIFEST_SHA256, f"首发清单 SHA-256 不符，预期 {MANIFEST_SHA256}，实际 {digest}")
        manifest = read_json(args.manifest)
        require(manifest["release"] == RELEASE and manifest["nugetSource"] == NUGET_SOURCE, "发行目标不符")
        packages = [args.package] if isinstance(args.package, str) else args.package or []
        for name in packages:
            require(name in manifest["packages"], f"首发清单不存在包 {name}")
        handoff, work = args.handoff.resolve(), args.work.resolve()
        require(handoff.is_dir() and not work.is_relative_to(handoff), "交接目录须存在且核验目录须位于交接目录外")
        work.mkdir(parents=True, exist_ok=True)
        with (work / "progress.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            progress = Progress(manifest, digest, handoff, work, NuGet(args.timeout), Dotnet(work))
            if args.command == "record":
                progress.record(args.kind, args.package, args.outcome, args.evidence, args.owner, args.upload_sha256)
                return 0
            if args.command == "gate":
                return progress.gate(args.package)
            return progress.verify(packages or manifest["publishOrder"], args.main_only)
    except (BadZipFile, KeyError, OSError, ValueError, VerificationError) as error:
        print(f"公开核验出错：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
