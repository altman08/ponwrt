# PonWrt

English | [简体中文](README_zh.md)

PonWrt is based on [ImmortalWrt](https://github.com/immortalwrt/immortalwrt) and adds support for Airoha AN7581 and AN7583 PON devices.

## Changes in `dev` compared with `master`

This overview describes the net changes at `dev` commit `7010562eb6`, compared with `master` commit `d9dd3a49f7`. See the [branch comparison](https://github.com/altman08/ponwrt/compare/master...dev). It covers the final configuration and implementation, including features supplied by the custom feeds; reverted experiments are not listed as enabled features. Unless stated otherwise, configuration changes apply to both `configs/an7581.config` and `configs/an7583.config`.

| Module | Change | Description / purpose | Default / scope | Configuration or implementation |
| --- | --- | --- | --- | --- |
| Package feeds | Track custom development feeds | Use `altman08/immortalwrt-packages;dev` and `altman08/immortalwrt-luci;dev`; add feeds for networking tools, cloud storage, USB sharing, Songloft and PicoClaw. Feed updates follow branches rather than fixed commits. | Used when updating feeds | [feeds.conf.default](feeds.conf.default) |
| Device profiles | Adjust the default AN7581 image set | Disable the HG5585F CT/CU and Nokia XG-040G-MD UBI `usb-sfp` variants in the supplied configuration; the device definitions remain available. | AN7581 configuration only | [configs/an7581.config](configs/an7581.config) |
| NPU / PON monitoring | Add Airoha status and PON tools | Include `luci-app-airoha-npu`, `luci-app-pon-status` and the PON overview translation. The custom NPU app exposes FE/PSE/PPE state, Ethernet topology, PON status and paginated PPE entries; its CPU history charts have been removed. | Selected in both configurations; available fields depend on hardware | [configs/](configs/), [NPU feed documentation](https://github.com/altman08/immortalwrt-luci/tree/dev/applications/luci-app-airoha-npu) |
| CPU controls | Add runtime cpufreq and PLL controls | The NPU app supports governor / frequency limits and a separate manual PLL control. Settings are not saved to UCI; each boot applies `ondemand` with a 1200 MHz ceiling when supported. | Airoha devices; manual PLL range is 500–1600 MHz | [NPU feed documentation](https://github.com/altman08/immortalwrt-luci/tree/dev/applications/luci-app-airoha-npu) |
| Temperature display | Extend autocore to Airoha | Install `tempinfo` on Airoha and report CPU, detected Wi-Fi and PON temperatures; PON readings come from `ponctl` using the configured optical device. | Display depends on available sensors and PON data | [autocore](package/emortal/autocore/) |
| Passwall | Include a configuration centered on Xray | Enable Passwall and geodata; disable its optional HAProxy, Sing-Box, Shadowsocks Rust, Simple-Obfs and V2ray-Plugin selections. Xray is selected through the Passwall dependency. | Both configurations | [configs/](configs/), [custom LuCI feed](https://github.com/altman08/immortalwrt-luci/tree/dev/applications/luci-app-passwall) |
| Xray Lite | Add an optional reduced client build | `CONFIG_PACKAGE_xray-core_INCLUDE_LITE=y` selects `xray_lite`. Keep SOCKS with HTTP fallback, tunnel / REDIRECT / TPROXY, VLESS outbound with RAW/TCP, TLS/REALITY/Vision, VLESS reverse proxy, UDP/XUDP, routing, direct/block and socket options. Exclude other proxy protocols/transports, API, custom DNS/FakeDNS, ECH, FinalMask and routing scripts. | Lite enabled in both configurations; disabling the option restores the full build | [Xray feed and Lite documentation](https://github.com/altman08/immortalwrt-packages/tree/dev/net/xray-core) |
| Xray EIP93 | Retain AES-GCM / AES-CBC acceleration | Carry the private Go overlay in patches 190–192. `XRAY_EIP93=auto` tries devcrypto, then AF_ALG, then Go software; hardware/CPU checks and failure fallback remain in place. The Lite build retains the overlay. | Runtime hardware path gated to AN7581; not an AN7583 acceleration claim | [EIP93 documentation](https://github.com/altman08/immortalwrt-packages/blob/dev/net/xray-core/README.eip93.md) |
| OpenSSL / kernel crypto | Include engines without enabling them globally | Select EIP93, CBC/CTR, crypto-user, cryptodev, OpenSSL AF_ALG/devcrypto modules and `openssl-util`. Newly generated OpenSSL engine configuration defaults AF_ALG/devcrypto to disabled; Xray's private backend is controlled separately. | Packages selected in both configurations; acceleration still depends on the device | [include/openssl-module.mk](include/openssl-module.mk), [configs/](configs/) |
| VPN / UDP tunnels | Add protocol interfaces and UDP tools | Select WireGuard tools and LuCI support, `luci-proto-n2n`, `luci-proto-tinyfecvpn`, `luci-app-udp2raw-ultra` and `luci-app-udpspeeder`. | Packages selected in both configurations; configure each service separately | [configs/](configs/), [feeds.conf.default](feeds.conf.default) |
| NAT / traffic handling | Add NAT and traffic utilities | Select NATMap, NAT mode management, FakeHTTP, FakeSIP and Wake-on-LAN / `etherwake`. | Packages selected in both configurations | [configs/](configs/) |
| Storage / file sharing | Add storage and file management tools | Select ksmbd, FileBrowser, hd-idle, loop devices, `lsblk`, exFAT and SquashFS packing/unpacking tools; build FUSE as a module (`m`). Remove VFAT from the default Airoha USB storage package list and disable it in both configurations. | Both configurations; ext4/exFAT remain in the USB storage package list | [configs/](configs/), [Airoha image Makefile](target/linux/airoha/image/Makefile) |
| LuCI file management / NAS | Customize FileBrowser and menu placement | Adapt FileBrowser to Argon, including light/dark layouts, sorting/filtering and queued uploads; move ksmbd's Network Shares entry to the NAS menu. | Custom LuCI feed; both apps selected in the supplied configurations | [FileBrowser](https://github.com/altman08/immortalwrt-luci/tree/dev/applications/luci-app-filebrowser), [ksmbd](https://github.com/altman08/immortalwrt-luci/tree/dev/applications/luci-app-ksmbd) |
| Cloud storage / USB sharing | Add WebDAV and USB sharing interfaces | Select the QuarkDrive WebDAV and VirtualHere LuCI apps and register their external feeds. Some backend packages are supplied by the release workflow's prebuilt APK step. | LuCI apps selected in both configurations; backend installation depends on packaging | [feeds.conf.default](feeds.conf.default), [release workflow](.github/workflows/release.yml) |
| IPTV / media | Add IPTV management and streaming | Select IPTV, IPTV scanning and `rtp2httpd`. Custom feeds include IPTV scan UI/translation changes and an updated `rtp2httpd` init script. | Both configurations | [configs/](configs/), [custom package feed](https://github.com/altman08/immortalwrt-packages/tree/dev/net/rtp2httpd) |
| Songloft / PicoClaw | Add application interfaces | Add the Songloft and PicoClaw feeds and select their LuCI apps. Their backend package symbols are not explicitly enabled in the supplied configs; the release workflow also installs prebuilt APKs. PushBot's feed is registered, but its app is disabled. | LuCI apps selected in both configurations; PushBot disabled | [configs/](configs/), [feeds.conf.default](feeds.conf.default) |
| Monitoring / diagnostics | Expand status and inspection tools | Select LuCI Dashboard, statistics, collectd with cpufreq/df/disk/thermal/UBI plugins, vnStat2, ramfree, fastfetch, htop, tmux and jq. Enable `CONFIG_KERNEL_PROC_PAGE_MONITOR` for detailed process-memory inspection. | Both configurations; custom LuCI feed adds UBI statistics support | [configs/](configs/), [UBI statistics documentation](https://github.com/altman08/immortalwrt-luci/tree/dev/applications/luci-app-statistics) |
| Remote access / FTP | Add tools for on-demand services | Enable Dropbear inetd mode support and select xinetd with its LuCI app, ShellInABox and BusyBox FTP tools. Enable BusyBox ftpd authentication and uploads. Selecting inetd support does not itself switch an existing SSH service to on-demand operation. | Packages/features selected in both configurations | [configs/](configs/) |
| BusyBox | Restore applets and diagnostic features | Enable tools including `pmap`, `lsof`, `fuser`, `iostat`, `mpstat`, `vmstat`, `watch`, `losetup`, `lsusb`, `httpd`, `tcpsvd` and `udpsvd`; extend archive, mount, account, text and editor support. Enable `FEATURE_SYSLOG_INFO` for normal informational log priority. | Both custom BusyBox configurations | [configs/](configs/) |
| Certificates / scripting | Add ACME and script dependencies | Select ACME with the DNS API scripts and LuCI app, QuickJS, and Lua argparse/cjson/curl-v3/FFI packages. | Both configurations | [configs/](configs/) |
| CI / target selection | Make SoC and recovery builds selectable | Choose AN7581 and AN7583 independently, require at least one target and build `recovery.itb` only when requested. | AN7581 on, AN7583 off, recovery off by default | [release workflow](.github/workflows/release.yml) |
| CI / staging cache | Build and reuse this repository's own tools | Fingerprint and verify host tools, toolchains and Go/Rust caches; restore from Actions or a Release backup, rebuild on a miss, and retain the latest cache per SoC. Target builds and signing keys are excluded. | `use_staging_cache=true` by default | [cache guide](docs/staging-cache.md), [cache script](scripts/staging-cache.py), [tests](scripts/tests/test_staging_cache.py) |
| CI / prebuilt packages | Install APKs before assembling images | Download APK assets from the `altman08/ponwrt` `prebuild-package` Release, reject duplicate locally built packages, and pass their names through `PREBUILT_APK_PACKAGES`. That installation path permits untrusted APKs. | Release workflow; ordinary local `make` does not download these APKs automatically | [release workflow](.github/workflows/release.yml), [package/Makefile](package/Makefile) |
| CI / diagnostics | Share dependency setup and preserve failure details | Use one dependency-install script; rerun failed build stages with `-j1 V=s`, upload failure logs, collect images by SoC and generate release checksums. | GitHub Actions release builds | [dependency script](scripts/ci-build-dependencies.sh), [release workflow](.github/workflows/release.yml) |
| Build system / workspace | Support feed-root packages and local work areas | Normalize root-level package Makefile paths during scanning; ignore the local `feed/` checkout directory and `.staging-cache/` archives. | Build metadata and developer workspace | [include/scan.mk](include/scan.mk), [.gitignore](.gitignore) |

Package selection in these tables means build/install configuration, not that every service starts automatically. Custom feed implementations are versioned in separate repositories and may change when feeds are updated. The main repository does not track local `feed/` checkouts.

Passwall still exposes options for the full Xray feature set: Lite capability-based UI and subscription filtering have not been implemented. With Lite enabled, use compatible node and DNS settings; unsupported configurations can fail to start. External DNS tools, firewall-based routing, SOCKS HTTP fallback and VLESS reverse proxy remain distinct from the removed Xray features. The approximately 14.81 MiB ARM64 static binary measured during Lite development is a reference result, not a fixed OpenWrt package size; toolchain and build parameters affect the output.

## ⚠️ Disclaimer

PonWrt is an open-source firmware project intended for research and development.

Flashing firmware or modifying PON-related settings involves risks and may result in boot failure, loss of configuration or device-specific data, or failure to register with the PON network. Please back up the original firmware and device data before making any changes.

Users are responsible for ensuring that their use complies with applicable laws, regulations, and network operator requirements. Do not use this project for unauthorized network access, impersonating or cloning another device's identity, or interfering with operator networks.

The authors and contributors are not responsible for device damage, network service disruption, or other consequences resulting from flashing, configuring, or using this project.

## Supported devices

| SoC | Device | Profile | Stock calibration / identity data |
| --- | --- | --- | --- |
| AN7581 | FiberHome HG5382A | `fiberhome_hg5382a` | `factory` |
| AN7581 | FiberHome HG5585F CT | `fiberhome_hg5585f-ct` | `factory` |
| AN7581 | FiberHome HG5585F CU | `fiberhome_hg5585f-cu` | `factory` |
| AN7581 | Gemtek XG2010G | `gemtek_xg2010g` | `dsd` |
| AN7581 | Nokia XG-040G-MD UBI | `nokia_xg-040g-md-ubi` | `bosa`, `ri` |
| AN7581 | Nokia XG-040G-TF UBI | `nokia_xg-040g-tf-ubi` | `bosa`, `ri` |
| AN7581 | UnionMan UNG00A | `unionman_ung00a` | `reservearea` |
| AN7581 | ZNXT ZN504XG-D | `znxt_zn504xg-d` | `reservearea` |
| AN7581 | ZNXT ZN515XG-D | `znxt_zn515xg-d` | `reservearea` |
| AN7581 | H3C HM2004-DU | `h3c_hm2004-du` | `factory` |
| AN7583 | Nokia XG-040G-MF | `nokia_xg-040g-mf`, `nokia_xg-040g-mf-ubi` | `bosa`, `ri` |

## Build

```sh
#  Install the required toolchain and libraries for building
sudo apt update -y
sudo apt full-upgrade -y
sudo apt install -y ack antlr3 asciidoc autoconf automake autopoint binutils bison build-essential \
  bzip2 ccache clang cmake cpio curl device-tree-compiler ecj fastjar flex gawk gettext gcc-multilib \
  g++-multilib git gnutls-dev gperf haveged help2man intltool lib32gcc-s1 libc6-dev-i386 libelf-dev \
  libglib2.0-dev libgmp3-dev libltdl-dev libmpc-dev libmpfr-dev libncurses-dev libpython3-dev \
  libreadline-dev libssl-dev libtool libyaml-dev libz-dev lld llvm lrzsz mkisofs msmtp nano \
  ninja-build p7zip p7zip-full patch pkgconf python3 python3-pip python3-ply python3-docutils \
  python3-pyelftools qemu-utils re2c rsync scons squashfs-tools subversion swig texinfo uglifyjs \
  upx-ucl unzip vim wget xmlto xxd zlib1g-dev zstd

#  Or use the ImmortalWrt one-click script to install dependencies
sudo bash -c 'bash <(curl -s https://build-scripts.immortalwrt.org/init_build_environment.sh)'


#  Clone the source code
git clone -b dev https://github.com/altman08/ponwrt.git
cd ponwrt


#  Update and install feeds (package sources)
./scripts/feeds update -a
./scripts/feeds install -a


#  Select a configuration, using 7581 as an example
cp configs/an7581.config .config
#  If the target is AN7583, use the following line instead:
cp configs/an7583.config .config



#  Start building
# -j$(nproc) means compiling in parallel with all CPU cores to speed things up
make defconfig
make -j$(nproc)
```

Images are written to `bin/targets/airoha/an7581/` or `bin/targets/airoha/an7583/`.

In GitHub Actions, **Release PonWrt** lets you select `an7581` and `an7583` independently. Only `an7581` is selected by default, and at least one SoC is required. The `recovery` option is off by default, disabling initramfs compilation so no `recovery.itb` is built. Enable it to build both recovery and sysupgrade images.

In GitHub Actions, **Release PonWrt** automatically builds and updates this repository's host tools, toolchain and Go/Rust cache when `use_staging_cache` is enabled (the default). Only the latest cache for each SoC is retained. See the [staging cache guide (Chinese)](docs/staging-cache.md).

## Install

Use [AN758x-Stock2UBI](https://github.com/pbs05/an758x-stock2ubi) to back up the stock flash and install the UBI layout. Boot images and Web recovery are provided by [AN758x U-Boot](https://github.com/pbs05/uboot-an758x).

After installing PonWrt, restore the stock calibration and identity data through U-Boot Web or **Network → PON → Configuration → PON board data** in LuCI. Convert FiberHome `factory` backups with [FiberHome Factory](https://github.com/pbs05/fiberhome-factory) first. Restore converted FiberHome data, `reservearea`, or `dsd` backups to the PonWrt `factory` volume. Nokia `bosa` and `ri` backups use volumes with the same names.
