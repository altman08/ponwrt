#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise cache invalidation, real archive round trips and cold-build fallback."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


spec = importlib.util.spec_from_file_location(
    "staging_cache", str(Path(__file__).resolve().parents[1] / "staging-cache.py"))
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


class StagingCacheTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ponwrt-cache-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "openwrt"
        self.root.mkdir()
        self.artifacts = Path(self.temporary.name) / "cache"
        self.write(".config", 'CONFIG_TARGET_BOARD="airoha"\nCONFIG_TARGET_SUBTARGET="an7581"\n'
                   'CONFIG_ARCH="aarch64"\nCONFIG_GCC_VERSION="14.4.0"\nCONFIG_USE_MUSL=y\n'
                   'CONFIG_PACKAGE_demo=y\n')
        self.write("include/host-build.mk", "# host build rules\n")
        self.write("toolchain/gcc/patches/fix.patch", "compiler patch\n")
        self.write("package/host-demo/Makefile", "$(eval $(call HostBuild))\n")
        self.write("package/host-demo/src.c", "int demo;\n")
        self.write("package/target-demo/Makefile", "$(eval $(call BuildPackage,demo))\n")
        self.write("feeds/packages/lang/golang/golang-version.mk", "GO_DEFAULT_VERSION:=1.27\n")
        self.write("feeds/packages/lang/rust/Makefile", "$(eval $(call HostBuild))\n")
        self.write("feeds.conf.default", "src-git packages https://example.invalid/packages.git\n")
        linked = self.root / "package/feeds/packages/rust"
        linked.parent.mkdir(parents=True)
        linked.symlink_to(self.root / "feeds/packages/lang/rust", target_is_directory=True)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "add", "."], cwd=str(self.root), check=True)
        subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "user.name=Cache Test", "-c", "user.email=cache@example.invalid",
                        "commit", "-qm", "fixture"], cwd=str(self.root), check=True)

    def write(self, name, content, executable=False):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if executable:
            path.chmod(0o755)
        return path

    def payload(self):
        # Stand-ins run real host GCC for the link smoke check; no cross compiler
        # or firmware build is needed to test the archive protocol.
        self.write("staging_dir/toolchain-test/bin/aarch64-openwrt-linux-musl-gcc",
                   '#!/bin/sh\nif [ "$1" = -dumpmachine ]; then\n'
                   'echo aarch64-openwrt-linux-musl\nelse exec gcc "$@"; fi\n', True)
        self.write("staging_dir/hostpkg/lib/go-1.27/bin/go",
                   "#!/bin/sh\necho 'go version go1.27 linux/amd64'\n", True)
        self.write("staging_dir/target-test/host/bin/rustc",
                   "#!/bin/sh\necho 'rustc 1.96.0'\n", True)
        self.write("staging_dir/target-test/host/bin/cargo",
                   "#!/bin/sh\necho 'cargo 1.96.0'\n", True)
        host_bin = self.root / "staging_dir/host/bin"
        host_bin.mkdir(parents=True)
        (host_bin / "gcc").symlink_to(shutil.which("gcc"))
        for name in ("staging_dir/host/stamp/.tools_compile_yyy",
                     "staging_dir/toolchain-test/stamp/.toolchain_compile",
                     "staging_dir/toolchain-test/stamp/.gcc_final_installed",
                     "staging_dir/hostpkg/stamp/.demo_installed",
                     "build_dir/hostpkg/demo/.prepared_abc",
                     "build_dir/hostpkg/demo/.configured",
                     "build_dir/hostpkg/demo/.built",
                     "build_dir/target-test/host/rust/.built"):
            self.write(name, "")
        self.write("staging_dir/target-test/root-test/secret", "not a cache input")
        self.write("build_dir/target-test/linux/vmlinux", "not a cache input")

    def packed(self):
        data = cache.context(self.root)
        self.payload()
        cache.pack(self.root, self.artifacts, data)
        shutil.rmtree(str(self.root / "staging_dir"))
        shutil.rmtree(str(self.root / "build_dir"))
        return data

    def test_cold_build_creates_aggregate_stamps_before_packing(self):
        self.payload()
        (self.root / "staging_dir/toolchain-test/stamp/.toolchain_compile").unlink()
        for package in ("golang-bootstrap", "golang"):
            self.write("package/feeds/packages/{}/Makefile".format(package), "")
        self.write("tmp/.build", "")
        source = Path(__file__).resolve().parents[2]
        # Use OpenWrt's real stamp rules with lightweight compile recipes.
        # Installing the tools alone must reproduce the original failure.
        self.write("Makefile", (
            "TMP_DIR := tmp\n"
            "SCRIPT_DIR := {source}/scripts\n"
            "include {source}/include/subdir.mk\n"
            "$(eval $(call stampfile,tools,tools,compile,,_yyy,staging_dir/host))\n"
            "$(eval $(call stampfile,toolchain,toolchain,compile,"
            "staging_dir/toolchain-test/stamp/.gcc_final_installed,,staging_dir/toolchain-test))\n"
            "prepare: .config $(tools/stamp-compile) $(toolchain/stamp-compile)\n"
            "tools/install: tools/compile\n"
            "toolchain/install: toolchain/compile\n"
            ".PHONY: tools/compile toolchain/compile\n"
            "tools/compile toolchain/compile tools/download toolchain/download:\n\t@:\n"
            "package/feeds/packages/%/download package/feeds/packages/%/host/compile:\n\t@:\n"
        ).format(source=source))
        subprocess.run(["make", "tools/install", "toolchain/install"],
                       cwd=str(self.root), check=True)
        with self.assertRaisesRegex(ValueError, "Missing toolchain compile stamp"):
            cache.validate(self.root)
        with contextlib.redirect_stdout(io.StringIO()):
            cache.build(self.root)
            data = cache.context(self.root)
            cache.pack(self.root, self.artifacts, data)
        archive, metadata = cache.paths_for(self.artifacts, data)
        self.assertTrue(archive.is_file())
        self.assertTrue(metadata.is_file())

    def test_fresh_checkout_mtimes_and_target_only_changes_keep_key(self):
        first = cache.context(self.root)
        host = self.root / "package/host-demo"

        def prepared_hash():
            listing = subprocess.check_output([
                "find", str(host), "-type", "f", "-printf", "%p%T@\n"])
            return hashlib.md5(b"\n".join(sorted(listing.splitlines()))).hexdigest()

        initial_stamp_hash = prepared_hash()
        os.utime(str(host / "src.c"), (1700000000, 1700000000))
        config = self.root / ".config"
        config.write_text(config.read_text() + 'CONFIG_PACKAGE_new_ui=y\nCONFIG_VERSION_NUMBER="new"\n')
        self.write("package/target-demo/ui.js", "updated UI")
        second = cache.context(self.root)
        self.assertEqual(first["key"], second["key"])
        # OpenWrt's mtime-based .prepared hash must also survive a new checkout.
        self.assertEqual(initial_stamp_hash, prepared_hash())

    def test_busybox_config_changes_keep_key(self):
        config = (self.root / ".config").read_text()
        initial = cache.context(self.root)["key"]
        for busybox in (
                "CONFIG_BUSYBOX_CUSTOM=y\nCONFIG_BUSYBOX_CONFIG_AWK=y\n",
                "CONFIG_BUSYBOX_CUSTOM=y\nCONFIG_BUSYBOX_CONFIG_SED=y\n"
                "CONFIG_BUSYBOX_CONFIG_FEATURE_EDITING_HISTORY=256\n",
                "CONFIG_BUSYBOX_CUSTOM=y\nCONFIG_BUSYBOX_CONFIG_SED=y\n"
                "CONFIG_BUSYBOX_CONFIG_FEATURE_EDITING_HISTORY=512\n",
                "CONFIG_BUSYBOX_DEFAULT_AWK=y\n",
                ""):
            with self.subTest(busybox=busybox):
                self.write(".config", config + busybox)
                self.assertEqual(initial, cache.context(self.root)["key"])

    def test_dropbear_and_openssl_config_changes_keep_key(self):
        config = (self.root / ".config").read_text()
        initial = cache.context(self.root)["key"]
        for options in (
                "CONFIG_DROPBEAR_SCP=y\nCONFIG_DROPBEAR_AUTH_TIMEOUT=300\n",
                "CONFIG_DROPBEAR_AUTH_TIMEOUT=600\n",
                "CONFIG_OPENSSL_WITH_TLS13=y\nCONFIG_OPENSSL_ENGINE=y\n",
                "CONFIG_OPENSSL_WITH_TLS13=y\n",
                ""):
            with self.subTest(options=options):
                self.write(".config", config + options)
                self.assertEqual(initial, cache.context(self.root)["key"])

    def test_host_patches_and_abi_options_invalidate_cache(self):
        initial = cache.context(self.root)["key"]
        patch = self.write("toolchain/gcc/patches/fix.patch", "changed compiler patch\n")
        changed = cache.context(self.root)["key"]
        self.assertNotEqual(initial, changed)
        patch.write_text("compiler patch\n")
        self.assertEqual(initial, cache.context(self.root)["key"])
        self.write(".config", (self.root / ".config").read_text().replace("CONFIG_USE_MUSL=y", "CONFIG_USE_GLIBC=y"))
        self.assertNotEqual(initial, cache.context(self.root)["key"])

    def test_shared_go_definitions_and_linked_host_sources_invalidate_cache(self):
        initial = cache.context(self.root)["key"]
        self.write("feeds/packages/lang/golang/golang-version.mk", "GO_DEFAULT_VERSION:=1.28\n")
        changed = cache.context(self.root)["key"]
        self.assertNotEqual(initial, changed)
        self.write("feeds/packages/lang/rust/patches/new.patch", "rust patch\n")
        self.assertNotEqual(changed, cache.context(self.root)["key"])

    def test_fresh_checkout_can_reuse_mtime_named_host_prepare_stamp(self):
        data = cache.context(self.root)
        source = self.root / "package/host-demo"

        def prepare_name():
            listing = subprocess.check_output([
                "find", str(source), "-type", "f", "-printf", "%p%T@\n"])
            checksum = hashlib.md5(b"\n".join(sorted(listing.splitlines()))).hexdigest()
            return "build_dir/hostpkg/demo/.prepared" + checksum

        self.payload()
        self.write(prepare_name(), "")
        cache.pack(self.root, self.artifacts, data)
        shutil.rmtree(str(self.root / "staging_dir"))
        shutil.rmtree(str(self.root / "build_dir"))
        os.utime(str(source / "src.c"), (1800000000, 1800000000))
        refreshed = cache.context(self.root)
        self.assertEqual(data["key"], refreshed["key"])
        cache.restore_archive(self.root, self.artifacts, refreshed)
        # Rebuilding any link in the prepared -> configured -> built -> installed
        # chain fails this check; an unchanged checkout should run no recipes.
        makefile = self.write("check.mk", (
            "staging_dir/hostpkg/stamp/.demo_installed: build_dir/hostpkg/demo/.built\n"
            "\t@exit 9\n"
            "build_dir/hostpkg/demo/.built: build_dir/hostpkg/demo/.configured\n"
            "\t@exit 9\n"
            "build_dir/hostpkg/demo/.configured: {}\n"
            "\t@exit 9\n"
            "{}: package/host-demo/src.c package/host-demo/Makefile\n"
            "\t@exit 9\n").format(prepare_name(), prepare_name()))
        subprocess.run(["make", "--no-print-directory", "-f", str(makefile)],
                       cwd=str(self.root), check=True)

    def test_round_trip_excludes_firmware_and_refreshes_real_stamps(self):
        data = self.packed()
        original_utime = os.utime

        def utime(path, times):
            self.assertFalse(Path(path).is_symlink(), "Do not touch system tools through cached symlinks")
            return original_utime(path, times)

        with mock.patch.object(os, "utime", side_effect=utime):
            cache.restore_archive(self.root, self.artifacts, data)
        self.assertTrue((self.root / "build_dir/hostpkg/demo/.built").is_file())
        self.assertFalse((self.root / "build_dir/target-test/linux").exists())
        self.assertFalse((self.root / "staging_dir/target-test/root-test").exists())
        self.assertFalse((self.root / "tools/stamp-compile").exists())
        self.assertGreaterEqual(
            (self.root / "staging_dir/hostpkg/stamp/.demo_installed").stat().st_mtime,
            (self.root / "build_dir/hostpkg/demo/.built").stat().st_mtime)

    def test_bad_checksum_and_wrong_key_do_not_extract_any_tools(self):
        data = self.packed()
        archive, _ = cache.paths_for(self.artifacts, data)
        with archive.open("ab") as stream:
            stream.write(b"corrupt")
        with self.assertRaisesRegex(ValueError, "checksum"):
            cache.restore_archive(self.root, self.artifacts, data)
        self.assertFalse((self.root / "staging_dir").exists())
        wrong = dict(data, fingerprint="different")
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            cache.restore_archive(self.root, self.artifacts, wrong)

    def test_unexpected_target_payload_is_rejected_before_extraction(self):
        data = self.packed()
        archive, metadata = cache.paths_for(self.artifacts, data)
        self.write("build_dir/target-test/linux/vmlinux", "forbidden firmware")
        subprocess.run(["tar", "-I", "zstd", "-cf", str(archive),
                        "build_dir/target-test/linux/vmlinux"], cwd=str(self.root), check=True)
        manifest = json.loads(metadata.read_text())
        manifest["sha256"] = cache.digest(archive)
        metadata.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "Unexpected cache entry"):
            cache.restore_archive(self.root, self.artifacts, data)
        self.assertFalse((self.root / "staging_dir").exists())

    def test_failed_tool_smoke_check_removes_restored_stamps(self):
        data = self.packed()
        with mock.patch.object(cache, "validate", side_effect=ValueError("broken compiler")):
            with self.assertRaisesRegex(ValueError, "broken compiler"):
                cache.restore_archive(self.root, self.artifacts, data)
        self.assertFalse((self.root / "staging_dir/toolchain-test").exists())
        self.assertFalse((self.root / "build_dir/hostpkg/demo/.built").exists())

    def test_invalid_manifest_is_a_cold_build(self):
        data = self.packed()
        _, metadata = cache.paths_for(self.artifacts, data)
        metadata.write_text("[]")
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            cache.restore(self.root, self.artifacts, data, False)
        self.assertIn("restored=false", stream.getvalue())
        self.assertFalse((self.root / "staging_dir").exists())

    def test_missing_cache_is_a_normal_cold_build(self):
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            cache.restore(self.root, self.artifacts, cache.context(self.root), False)
        self.assertIn("restored=false", stream.getvalue())

    def test_corrupt_actions_cache_can_fall_back_to_release(self):
        data = self.packed()
        backup = Path(self.temporary.name) / "release"
        shutil.copytree(str(self.artifacts), str(backup))
        archive, _ = cache.paths_for(self.artifacts, data)
        archive.write_bytes(b"corrupt")
        original_run = subprocess.run

        def run(command, **kwargs):
            if command[0] == "gh":
                for asset in backup.iterdir():
                    shutil.copy2(str(asset), str(self.artifacts / asset.name))
                return subprocess.CompletedProcess(command, 0)
            return original_run(command, **kwargs)

        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "example/ponwrt"}), \
                mock.patch.object(subprocess, "run", side_effect=run), \
                contextlib.redirect_stdout(io.StringIO()) as stream:
            cache.restore(self.root, self.artifacts, data, True)
        self.assertIn("restored=true", stream.getvalue())
        self.assertIn("source=release", stream.getvalue())

    def test_publish_uploads_before_removing_only_old_assets_for_its_soc(self):
        data = self.packed()
        archive, metadata = cache.paths_for(self.artifacts, data)
        assets = [
            {"id": 1, "name": "ponwrt-staging-v1-airoha-an7581-old.tar.zst"},
            {"id": 2, "name": "ponwrt-staging-v0-airoha-an7581-old.json"},
            {"id": 3, "name": "ponwrt-staging-v1-airoha-an7583-other.tar.zst"},
            {"id": 4, "name": "firmware.bin"},
            {"id": 5, "name": archive.name},
            {"id": 6, "name": metadata.name},
        ]
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "example/ponwrt"}), \
                mock.patch.object(cache, "ensure_cache_release", return_value=42), \
                mock.patch.object(cache, "github_items", return_value=assets), \
                mock.patch.object(subprocess, "run") as run:
            cache.publish(self.root, self.artifacts, data)
        commands = [call[0][0] for call in run.call_args_list]
        self.assertEqual(commands[0][:4], ["gh", "release", "upload", "staging-cache"])
        self.assertIn(str(archive), commands[0])
        self.assertIn(str(metadata), commands[0])
        self.assertEqual([command[-1] for command in commands[1:]], [
            "repos/example/ponwrt/releases/assets/1", "repos/example/ponwrt/releases/assets/2"])

    def test_failed_upload_keeps_previous_release_backup(self):
        data = self.packed()
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "example/ponwrt"}), \
                mock.patch.object(cache, "ensure_cache_release", return_value=42), \
                mock.patch.object(cache, "github_items", return_value=[
                    {"id": 1, "name": "ponwrt-staging-v1-airoha-an7581-old.tar.zst"}]), \
                mock.patch.object(subprocess, "run", side_effect=subprocess.CalledProcessError(1, "upload")) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                cache.publish(self.root, self.artifacts, data)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args[0][0][1:3], ["release", "upload"])

    def test_identical_release_backup_skips_upload_but_prunes_old_assets(self):
        data = self.packed()
        archive, metadata = cache.paths_for(self.artifacts, data)
        assets = [{"id": 1, "name": archive.name, "digest": "sha256:" + cache.digest(archive)},
                  {"id": 2, "name": metadata.name, "digest": "sha256:" + cache.digest(metadata)},
                  {"id": 3, "name": "ponwrt-staging-v1-airoha-an7581-old.json"}]
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "example/ponwrt"}), \
                mock.patch.object(cache, "ensure_cache_release", return_value=42), \
                mock.patch.object(cache, "github_items", return_value=assets), \
                mock.patch.object(subprocess, "run") as run:
            cache.publish(self.root, self.artifacts, data)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args[0][0], [
            "gh", "api", "--method", "DELETE", "repos/example/ponwrt/releases/assets/3"])

    def test_invalid_archive_is_not_published(self):
        data = self.packed()
        archive, _ = cache.paths_for(self.artifacts, data)
        archive.write_bytes(b"corrupt")
        with mock.patch.object(cache, "ensure_cache_release") as release:
            with self.assertRaisesRegex(ValueError, "checksum"):
                cache.publish(self.root, self.artifacts, data)
        release.assert_not_called()

    def test_first_release_creation_tolerates_other_soc_winning_race(self):
        with mock.patch.object(subprocess, "check_output", side_effect=[
                subprocess.CalledProcessError(1, "not found"), b'{"id": 42}']), \
                mock.patch.object(subprocess, "call", return_value=1) as create:
            self.assertEqual(cache.ensure_cache_release("example/ponwrt", "abc123"), 42)
        self.assertIn("--prerelease", create.call_args[0][0])
        self.assertIn("--latest=false", create.call_args[0][0])

    def test_actions_cleanup_keeps_current_snapshot_other_soc_and_downloads(self):
        data = cache.context(self.root)
        keeper = data["key"] + "-100-1"
        snapshots = [
            {"id": 1, "key": keeper},
            {"id": 2, "key": data["key"] + "-99-1"},
            {"id": 3, "key": "ponwrt-staging-v0-airoha-an7581-old-98-1"},
            {"id": 4, "key": "ponwrt-staging-v1-airoha-an7583-other-100-1"},
            {"id": 5, "key": "ponwrt-dl-an7581-sources"},
        ]
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "example/ponwrt"}), \
                mock.patch.object(cache, "github_items", return_value=snapshots), \
                mock.patch.object(subprocess, "run") as run:
            cache.prune_actions(data, keeper)
        self.assertEqual([call[0][0][-1] for call in run.call_args_list], [
            "repos/example/ponwrt/actions/caches/2", "repos/example/ponwrt/actions/caches/3"])

    def test_actions_cleanup_requires_a_visible_matching_keeper(self):
        data = cache.context(self.root)
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "example/ponwrt"}), \
                mock.patch.object(cache, "github_items", return_value=[
                    {"id": 1, "key": "ponwrt-staging-v1-airoha-an7581-old-99-1"}]), \
                mock.patch.object(subprocess, "run") as run:
            for keeper in (None, "wrong-key", data["key"] + "-100-1"):
                with self.assertRaises(ValueError):
                    cache.prune_actions(data, keeper)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
