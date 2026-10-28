#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Preheat and reuse OpenWrt host tools; never cache target firmware outputs."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time


SCHEMA = 1
# OpenWrt's default .prepared hash includes source mtimes. Fresh checkouts must
# have identical host-source mtimes, as well as identical contents, to reuse it.
SOURCE_TIME = 946684800
SCRIPT = Path(__file__).resolve()


def output(name, value):
    print("{}={}".format(name, value), flush=True)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            stream.write("{}={}\n".format(name, value))


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def files_under(directory):
    """Follow installed feed links, without following recursive feed links."""
    seen = set()
    for base, directories, names in os.walk(str(directory), followlinks=True):
        real = os.path.realpath(base)
        if real in seen:
            directories[:] = []
            continue
        seen.add(real)
        directories[:] = sorted(d for d in directories if not d.startswith("."))
        for name in sorted(names):
            if not name.startswith("."):
                path = Path(base) / name
                if path.is_file():
                    yield path


def configuration(root):
    values = {}
    for line in (root / ".config").read_text(encoding="utf-8").splitlines():
        match = re.match(r"(CONFIG_[A-Za-z0-9_]+)=(.*)$", line)
        if match:
            values[match[1]] = match[2].strip('"')
    if values.get("CONFIG_TARGET_BOARD") != "airoha":
        raise ValueError("Expected a defconfig-expanded Airoha configuration")
    if values.get("CONFIG_TARGET_SUBTARGET") not in ("an7581", "an7583"):
        raise ValueError("Expected AN7581 or AN7583")
    return values


def context(root):
    config = configuration(root)
    # Hash tracked source files, not binaries generated in scripts/config etc.
    tracked = subprocess.check_output([
        "git", "ls-files", "-z", "--", "include", "tools", "toolchain",
        "config", "scripts", "rules.mk", "Makefile",
        "target/linux/airoha/Makefile", "target/linux/airoha/Config.in",
        "target/linux/airoha/{}/target.mk".format(config["CONFIG_TARGET_SUBTARGET"]),
    ], cwd=str(root)).decode("utf-8").split("\0")
    inputs = {root / name for name in tracked if name and (root / name).is_file()}
    for name in ("scripts/ci-build-dependencies.sh", "feeds.conf", "feeds.conf.default"):
        if (root / name).is_file():
            inputs.add(root / name)

    # Include every installed HostBuild definition, its patches and local source.
    # Target-only packages and UI changes do not invalidate installed host tools.
    host_dirs = set()
    for path in files_under(root / "package"):
        if path.name == "Makefile":
            content = path.read_bytes()
            if b"HostBuild" in content or b"host-build.mk" in content:
                host_dirs.add(path.parent)
    for directory in sorted(host_dirs):
        inputs.update(files_under(directory))
    # Go shares build definitions with versioned/bootstrap sibling packages.
    for name in ("golang", "rust"):
        directory = root / "feeds/packages/lang" / name
        if not directory.is_dir():
            raise ValueError("Install the packages feed before computing the cache key")
        inputs.update(files_under(directory))

    hashes = {}
    for path in sorted(inputs):
        hashes[path.relative_to(root).as_posix()] = digest(path)
        if not path.is_symlink():
            os.utime(str(path), (SOURCE_TIME, SOURCE_TIME))
    hashes["scripts/staging-cache.py"] = digest(SCRIPT)

    # Keep build options conservatively: packages can introduce their own host
    # options (e.g. Python), so a toolchain-only allowlist would miss inputs.
    # BusyBox, Dropbear and OpenSSL options affect target packages, which are
    # not in this cache; host crypto tools use separate build definitions.
    ignored = ("CONFIG_PACKAGE_", "CONFIG_DEFAULT_", "CONFIG_MODULE_DEFAULT_",
               "CONFIG_BUSYBOX_", "CONFIG_DROPBEAR_", "CONFIG_OPENSSL_",
               "CONFIG_VERSION_", "CONFIG_VERSIONOPT",
               "CONFIG_TARGET_DEVICE", "CONFIG_TARGET_ROOTFS", "CONFIG_TARGET_INITRAMFS",
               "CONFIG_TARGET_SQUASHFS", "CONFIG_TARGET_UBIFS", "CONFIG_TARGET_MULTI_PROFILE",
               "CONFIG_TARGET_PER_DEVICE_ROOTFS", "CONFIG_TARGET_ALL_PROFILES")
    options = {key: value for key, value in config.items()
               if not key.startswith(ignored)}
    host = {
        "os": platform.system(), "arch": platform.machine(),
        "distribution": Path("/etc/os-release").read_text(encoding="utf-8"),
        "compiler": subprocess.check_output(["gcc", "--version"]).decode("utf-8").splitlines()[0],
    }
    data = {"schema": SCHEMA, "root": str(root), "host": host,
            "config": options, "inputs": hashes}
    fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
    prefix = "ponwrt-staging-v{}-airoha-{}-".format(SCHEMA, config["CONFIG_TARGET_SUBTARGET"])
    return dict(data, fingerprint=fingerprint, key=prefix + fingerprint, prefix=prefix)


def install_dirs(root):
    paths = [root / "staging_dir/host", root / "staging_dir/hostpkg"]
    paths += sorted(root.glob("staging_dir/toolchain-*"))
    paths += sorted(root.glob("staging_dir/target-*/host"))
    return [path for path in paths if path.is_dir()]


def build_bases(root):
    return [root / "build_dir/host", root / "build_dir/hostpkg"] + sorted(
        root.glob("build_dir/target-*/host"))


def build_stamps(root):
    for base in build_bases(root):
        for pattern in ("*/.prepared*", "*/.configured*", "*/.built"):
            for path in sorted(base.glob(pattern)):
                if path.is_file() and "_check" not in path.name:
                    yield path


def validate(root):
    """Require working tools and a linkable target executable, not just files."""
    compilers = sorted(root.glob("staging_dir/toolchain-*/bin/*-openwrt-linux-*-gcc"))
    go = [path for path in root.glob("staging_dir/hostpkg/lib/go-*/bin/go")
          if "go-bootstrap" not in str(path)]
    rust = sorted(root.glob("staging_dir/target-*/host/bin/rustc"))
    if not compilers or not go or not rust:
        raise ValueError("Incomplete cache: cross GCC, Go and Rust are required")
    compiler = compilers[0]
    if "aarch64" not in subprocess.check_output([str(compiler), "-dumpmachine"]).decode():
        raise ValueError("Cached compiler is not an AArch64 compiler")
    with tempfile.TemporaryDirectory(prefix="ponwrt-cache-check-") as directory:
        subprocess.run([str(compiler), "-x", "c", "-", "-o", directory + "/check"],
                       input=b"int main(void) { return 0; }\n", check=True)
    versions = {}
    for name, binary, argument in (("gcc", compiler, "--version"),
                                   ("go", sorted(go)[0], "version"),
                                   ("rustc", rust[0], "--version"),
                                   ("cargo", rust[0].with_name("cargo"), "--version")):
        versions[name] = subprocess.check_output(
            [str(binary), argument], stderr=subprocess.STDOUT).decode("utf-8").splitlines()[0]
    if not list(root.glob("staging_dir/host/stamp/.tools_compile_*")):
        raise ValueError("Missing tools compile stamp")
    if not list(root.glob("staging_dir/toolchain-*/stamp/.toolchain_compile")):
        raise ValueError("Missing toolchain compile stamp")
    return versions


def build(root):
    def make(*targets):
        command = ["make", "-j{}".format(os.cpu_count() or 2)] + list(targets)
        if subprocess.call(command, cwd=str(root)):
            subprocess.run(["make", "-j1", "V=s"] + list(targets), cwd=str(root), check=True)

    make("tools/download", "toolchain/download")
    # Direct */install targets do not create the aggregate compile stamps
    # required by validate() and by subsequent firmware builds.
    make("prepare")
    for package in ("golang-bootstrap", "golang", "rust"):
        directory = root / "package/feeds/packages" / package
        if not (directory / "Makefile").is_file():
            raise ValueError("Missing installed host package: " + package)
        target = directory.relative_to(root).as_posix()
        make(target + "/download")
        make(target + "/host/compile")
    print(json.dumps(validate(root), indent=2))


def paths_for(cache_dir, data):
    return cache_dir / (data["key"] + ".tar.zst"), cache_dir / (data["key"] + ".json")


def pack(root, cache_dir, data):
    versions = validate(root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive, metadata = paths_for(cache_dir, data)
    paths = install_dirs(root) + list(build_stamps(root))
    with tempfile.NamedTemporaryFile() as listing:
        listing.write(b"\0".join(str(path.relative_to(root)).encode("utf-8") for path in paths) + b"\0")
        listing.flush()
        subprocess.run(["tar", "-I", "zstd -T0 -3", "-cf", str(archive),
                        "--null", "-T", listing.name], cwd=str(root), check=True)
    manifest = dict(data, sha256=digest(archive), versions=versions,
                    commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root)).decode().strip())
    metadata.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("Packed {} ({:.1f} MiB)".format(archive.name, archive.stat().st_size / 1024 ** 2))


def allowed_member(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    parts = path.parts
    if len(parts) >= 2 and parts[0] == "staging_dir":
        return (parts[1] in ("host", "hostpkg") or parts[1].startswith("toolchain-")
                or (len(parts) >= 3 and parts[1].startswith("target-") and parts[2] == "host"))
    if parts and parts[0] == "build_dir":
        base = 2 if len(parts) >= 2 and parts[1] in ("host", "hostpkg") else 3
        return (len(parts) == base + 2
                and (base == 2 or (parts[1].startswith("target-") and parts[2] == "host"))
                and (parts[-1].startswith((".prepared", ".configured")) or parts[-1] == ".built"))
    return False


def check_archive(archive):
    process = subprocess.Popen(["zstd", "-dc", str(archive)], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as stream:
            for member in stream:
                if not allowed_member(member.name):
                    raise ValueError("Unexpected cache entry: " + member.name)
                if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                    raise ValueError("Unsupported cache entry: " + member.name)
                if member.islnk() and not allowed_member(member.linkname):
                    raise ValueError("Unexpected hardlink target: " + member.linkname)
        # Drain tar padding so the decompressor can exit normally.
        while process.stdout.read(1024 * 1024):
            pass
        if process.wait():
            raise ValueError("Corrupt zstd archive")
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.kill()
        process.wait()


def clear_payload(root):
    for path in install_dirs(root) + build_bases(root):
        if path.is_symlink():
            path.unlink()
        elif path.exists():
            shutil.rmtree(str(path))


def checked_manifest(root, cache_dir, data):
    archive, metadata = paths_for(cache_dir, data)
    manifest = json.loads(metadata.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Invalid cache manifest")
    if manifest.get("fingerprint") != data["fingerprint"] or manifest.get("root") != str(root):
        raise ValueError("Cache fingerprint or build path differs")
    if digest(archive) != manifest.get("sha256"):
        raise ValueError("Cache checksum differs")
    return manifest


def restore_archive(root, cache_dir, data):
    checked_manifest(root, cache_dir, data)
    archive, _ = paths_for(cache_dir, data)
    check_archive(archive)
    try:
        subprocess.run(["tar", "-I", "zstd -d", "-xf", str(archive), "--no-same-owner"],
                       cwd=str(root), check=True)
        validate(root)
        # Refresh the real OpenWrt stamps, not files named tools/stamp-compile
        # (those names are make variables, not the on-disk stamp paths).
        stamp_time = time.time()
        stamps = list(build_stamps(root))
        for directory in install_dirs(root):
            stamps += [path for path in directory.rglob("*")
                       if path.is_file() and not path.is_symlink()
                       and ("stamp" in path.parts or path.parent.name == "bin")]
        for stamp in stamps:
            os.utime(str(stamp), (stamp_time, stamp_time))
    except Exception:
        # A failed smoke check must not leave tools/stamps that skip rebuilding.
        clear_payload(root)
        raise


def restore(root, cache_dir, data, release):
    for source in (["actions", "release"] if release else ["actions"]):
        try:
            if source == "release":
                cache_dir.mkdir(parents=True, exist_ok=True)
                archive, metadata = paths_for(cache_dir, data)
                subprocess.run([
                    "gh", "release", "download", "staging-cache", "--repo", os.environ["GITHUB_REPOSITORY"],
                    "--pattern", archive.name, "--pattern", metadata.name,
                    "--dir", str(cache_dir), "--clobber",
                ], check=True)
            restore_archive(root, cache_dir, data)
            output("restored", "true")
            output("source", source)
            return
        except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
            print("Cache {} unavailable: {}".format(source, error), flush=True)
    output("restored", "false")
    output("source", "none")


def github_items(endpoint, selector=".[]"):
    # One JSON object per line keeps --paginate valid without assuming a page
    # count or relying on concatenated JSON arrays being a single document.
    result = subprocess.check_output([
        "gh", "api", "--paginate", endpoint, "--jq", selector + " | @json",
    ]).decode("utf-8")
    return [json.loads(line) for line in result.splitlines() if line.strip()]


def github_repository():
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not repository:
        raise ValueError("GITHUB_REPOSITORY is required for cache publication and cleanup")
    return repository


def same_target_cache(name, data):
    target = data["config"]["CONFIG_TARGET_SUBTARGET"]
    # Include previous schema versions when removing obsolete snapshots.
    return bool(re.match(r"^ponwrt-staging-(?:v[0-9]+-)?airoha-" + re.escape(target) + "-", name))


def ensure_cache_release(repository, commit):
    command = ["gh", "api", "repos/{}/releases/tags/staging-cache".format(repository)]
    try:
        return json.loads(subprocess.check_output(command).decode("utf-8"))["id"]
    except subprocess.CalledProcessError:
        # Both SoCs may reach the first publication together. If creation loses
        # the race, read the release created by the other job before giving up.
        subprocess.call([
            "gh", "release", "create", "staging-cache", "--repo", repository,
            "--target", commit, "--title", "Staging Build Cache",
            "--notes", "Latest host tools and toolchain cache for each SoC, maintained by release.yml.",
            "--prerelease", "--latest=false",
        ])
        return json.loads(subprocess.check_output(command).decode("utf-8"))["id"]


def publish(root, cache_dir, data):
    manifest = checked_manifest(root, cache_dir, data)
    repository = github_repository()
    archive, metadata = paths_for(cache_dir, data)
    release_id = ensure_cache_release(repository, manifest["commit"])
    assets = github_items("repos/{}/releases/{}/assets?per_page=100".format(repository, release_id))
    keep = {archive.name: "sha256:" + manifest["sha256"], metadata.name: "sha256:" + digest(metadata)}
    remote = {asset["name"]: asset.get("digest") for asset in assets}
    if not all(remote.get(name) == checksum for name, checksum in keep.items()):
        subprocess.run([
            "gh", "release", "upload", "staging-cache", str(archive), str(metadata),
            "--repo", repository, "--clobber",
        ], check=True)
    output("published", "true")
    # Never remove the previous backup until both new assets have uploaded.
    removed = 0
    for asset in assets:
        if (same_target_cache(asset["name"], data) and asset["name"] not in keep
                and asset["name"].endswith((".tar.zst", ".tzst", ".json"))):
            subprocess.run([
                "gh", "api", "--method", "DELETE",
                "repos/{}/releases/assets/{}".format(repository, asset["id"]),
            ], check=True)
            removed += 1
    output("release_pruned", removed)


def prune_actions(data, keep_key):
    if not keep_key or not keep_key.startswith(data["key"] + "-"):
        raise ValueError("Refusing to prune without a matching current cache snapshot")
    repository = github_repository()
    snapshots = github_items(
        "repos/{}/actions/caches?per_page=100&key=ponwrt-staging-".format(repository),
        ".actions_caches[]")
    if not any(snapshot["key"] == keep_key for snapshot in snapshots):
        raise ValueError("New Actions snapshot is not visible yet; keeping previous caches")
    removed = 0
    for snapshot in snapshots:
        if same_target_cache(snapshot["key"], data) and snapshot["key"] != keep_key:
            subprocess.run([
                "gh", "api", "--method", "DELETE",
                "repos/{}/actions/caches/{}".format(repository, snapshot["id"]),
            ], check=True)
            removed += 1
    output("actions_pruned", removed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fingerprint", "build", "pack", "restore", "publish", "prune-actions"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--cache-dir", default=".staging-cache")
    parser.add_argument("--release", action="store_true", help="Fall back to this repository's staging-cache release")
    parser.add_argument("--keep-key", help="Actions snapshot to retain when pruning this SoC's older caches")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    cache_dir = Path(args.cache_dir).resolve()
    data = context(root)
    if args.command == "fingerprint":
        output("key", data["key"])
        output("prefix", data["prefix"])
    elif args.command == "build":
        build(root)
    elif args.command == "pack":
        pack(root, cache_dir, data)
    elif args.command == "restore":
        restore(root, cache_dir, data, args.release)
    elif args.command == "publish":
        publish(root, cache_dir, data)
    else:
        prune_actions(data, args.keep_key)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
        print("::error::{}".format(error), file=sys.stderr)
        sys.exit(1)
