# PonWrt

[English](README.md) | 简体中文

PonWrt 基于 [ImmortalWrt](https://github.com/immortalwrt/immortalwrt)，增加了对 Airoha AN7581 和 AN7583 PON 设备的支持。

## `dev` 相对 `master` 的改动

以下按 `dev` 提交 `7010562eb6` 对比 `master` 提交 `d9dd3a49f7`，汇总分支的最终差异，完整文件差异见[分支对比](https://github.com/altman08/ponwrt/compare/master...dev)。表格包含自定义 feeds 提供的功能，不将已撤销的实验列为现有功能。除特别注明外，配置改动同时适用于 `configs/an7581.config` 和 `configs/an7583.config`。

| 模块 | 改动点 | 说明与作用 | 默认状态 / 适用范围 | 配置或实现位置 |
| --- | --- | --- | --- | --- |
| 软件包源 | 切换自定义开发源 | packages、luci 分别跟踪 `altman08/immortalwrt-packages;dev`、`altman08/immortalwrt-luci;dev`；增加网络工具、网盘、USB 共享、Songloft、PicoClaw 等源。更新 feeds 时跟随分支，不锁定提交。 | 更新 feeds 时生效 | [feeds.conf.default](feeds.conf.default) |
| 设备镜像 | 调整 AN7581 默认机型 | 配置中关闭 HG5585F CT/CU、Nokia XG-040G-MD UBI 的 `usb-sfp` 变体，设备定义仍保留。 | 仅 AN7581 默认配置 | [configs/an7581.config](configs/an7581.config) |
| NPU / PON 状态 | 增加 Airoha 状态及 PON 工具 | 选中 `luci-app-airoha-npu`、`luci-app-pon-status` 和 PON 概览中文翻译；自定义 NPU 页面提供 FE/PSE/PPE、网口拓扑、PON 状态和 PPE 分页，CPU 历史监控图表已移除。 | 两份配置均选中；显示内容取决于硬件 | [configs/](configs/)、[NPU 插件说明](https://github.com/altman08/immortalwrt-luci/tree/dev/applications/luci-app-airoha-npu) |
| CPU 调频 | 增加运行时 cpufreq 与 PLL 控制 | NPU 插件支持 governor、最高频率及独立手动 PLL 调频；不保存到 UCI，开机在硬件支持时应用 `ondemand` 和 1200 MHz 上限。 | Airoha 设备；手动 PLL 范围 500–1600 MHz | [NPU 插件说明](https://github.com/altman08/immortalwrt-luci/tree/dev/applications/luci-app-airoha-npu) |
| 温度显示 | 为 autocore 增加 Airoha 支持 | 在 Airoha 安装 `tempinfo`，显示 CPU、检测到的 Wi-Fi 和 PON 温度；PON 温度通过 `ponctl` 读取配置中的光口。 | 取决于传感器及 PON 数据是否可用 | [autocore](package/emortal/autocore/) |
| Passwall | 增加以 Xray 为核心的默认组合 | 开启 Passwall 与 geodata，关闭其可选的 HAProxy、Sing-Box、Shadowsocks Rust、Simple-Obfs、V2ray-Plugin；Xray 由 Passwall 依赖选入。 | 两份配置均启用 | [configs/](configs/)、[自定义 LuCI 源](https://github.com/altman08/immortalwrt-luci/tree/dev/applications/luci-app-passwall) |
| Xray 精简 | 增加可选客户端精简构建 | `CONFIG_PACKAGE_xray-core_INCLUDE_LITE=y` 启用 `xray_lite`；保留 SOCKS 及 HTTP 回退、tunnel / REDIRECT / TPROXY、VLESS 出站、RAW/TCP、TLS/REALITY/Vision、VLESS 反向代理、UDP/XUDP、路由、直连/阻断和套接字选项；排除其他代理协议/传输、API、自定义 DNS/FakeDNS、ECH、FinalMask、路由脚本等。 | 两份配置默认开启；关闭该选项恢复完整构建 | [Xray 源及精简说明](https://github.com/altman08/immortalwrt-packages/tree/dev/net/xray-core) |
| Xray EIP93 | 保留 AES-GCM / AES-CBC 加速 | 通过 190–192 补丁生成私有 Go overlay；`XRAY_EIP93=auto` 依次尝试 devcrypto、AF_ALG、Go 软件实现，保留硬件/CPU 检测及失败回退，精简版也保留该路径。 | 硬件路径在运行时限定 AN7581；不表示 AN7583 也使用该加速 | [EIP93 说明](https://github.com/altman08/immortalwrt-packages/blob/dev/net/xray-core/README.eip93.md) |
| OpenSSL / 内核加密 | 包含加密模块，默认不全局启用引擎 | 选中 EIP93、CBC/CTR、crypto-user、cryptodev、OpenSSL AF_ALG/devcrypto 模块及 `openssl-util`；新生成的 OpenSSL 引擎配置将 AF_ALG/devcrypto 默认设为关闭，Xray 私有后端另行控制。 | 两份配置均选中相关包；实际加速取决于设备 | [include/openssl-module.mk](include/openssl-module.mk)、[configs/](configs/) |
| VPN / UDP 隧道 | 增加协议接口与 UDP 工具 | 选中 WireGuard 工具及 LuCI、`luci-proto-n2n`、`luci-proto-tinyfecvpn`、`luci-app-udp2raw-ultra`、`luci-app-udpspeeder`。 | 两份配置均选中，服务需分别配置 | [configs/](configs/)、[feeds.conf.default](feeds.conf.default) |
| NAT / 流量处理 | 增加 NAT 及流量工具 | 选中 NATMap、NAT 模式管理、FakeHTTP、FakeSIP、网络唤醒及 `etherwake`。 | 两份配置均选中 | [configs/](configs/) |
| 存储 / 文件共享 | 增加存储与文件管理工具 | 选中 ksmbd、FileBrowser、hd-idle、loop、`lsblk`、exFAT、SquashFS 打包/解包工具，FUSE 编译为模块（`m`）；Airoha 默认 USB 存储包列表移除 VFAT，两份配置关闭 VFAT。 | 两份配置生效；默认 USB 存储包仍保留 ext4/exFAT | [configs/](configs/)、[Airoha 镜像配置](target/linux/airoha/image/Makefile) |
| LuCI 文件管理 / NAS | 调整 FileBrowser 界面及菜单 | FileBrowser 适配 Argon，支持明暗主题、排序筛选及上传队列；ksmbd 的网络共享入口移到 NAS 菜单。 | 自定义 LuCI 源实现；两份配置均选中这两个应用 | [FileBrowser](https://github.com/altman08/immortalwrt-luci/tree/dev/applications/luci-app-filebrowser)、[ksmbd](https://github.com/altman08/immortalwrt-luci/tree/dev/applications/luci-app-ksmbd) |
| 网盘 / USB 共享 | 增加 WebDAV 与 USB 共享界面 | 选中夸克网盘 WebDAV、VirtualHere 的 LuCI 应用并注册外部源；部分后端程序通过发布流程的预编译 APK 步骤装入。 | 两份配置均选中 LuCI；后端安装取决于打包流程 | [feeds.conf.default](feeds.conf.default)、[发布流程](.github/workflows/release.yml) |
| IPTV / 媒体 | 增加 IPTV 管理及流媒体工具 | 选中 IPTV、IPTV 扫描、`rtp2httpd`；自定义 feeds 包含扫描界面/翻译调整及 `rtp2httpd` 启动脚本更新。 | 两份配置均选中 | [configs/](configs/)、[自定义软件包源](https://github.com/altman08/immortalwrt-packages/tree/dev/net/rtp2httpd) |
| Songloft / PicoClaw | 增加应用界面 | 增加 Songloft、PicoClaw 源并选中 LuCI；配置中未显式启用其后端包符号，发布流程另有预编译 APK 安装步骤。PushBot 仅注册源，当前关闭其应用。 | 两份配置均选中 LuCI；PushBot 关闭 | [configs/](configs/)、[feeds.conf.default](feeds.conf.default) |
| 监控 / 诊断 | 扩充状态与检查工具 | 选中 LuCI Dashboard、statistics、collectd 及 cpufreq/df/disk/thermal/UBI 插件、vnStat2、ramfree、fastfetch、htop、tmux、jq；开启 `CONFIG_KERNEL_PROC_PAGE_MONITOR`，支持详细进程内存检查。 | 两份配置均生效；自定义 LuCI 源增加 UBI 统计支持 | [configs/](configs/)、[UBI 统计说明](https://github.com/altman08/immortalwrt-luci/tree/dev/applications/luci-app-statistics) |
| 远程访问 / FTP | 增加按需服务所需工具 | 开启 Dropbear inetd 模式支持，选中 xinetd 及 LuCI、ShellInABox、BusyBox FTP 工具，开启 ftpd 认证和上传；编译 inetd 支持本身不会自动将现有 SSH 服务改为按需启动。 | 两份配置均选中相关包/特性 | [configs/](configs/) |
| BusyBox | 恢复 applet 与诊断功能 | 开启 `pmap`、`lsof`、`fuser`、`iostat`、`mpstat`、`vmstat`、`watch`、`losetup`、`lsusb`、`httpd`、`tcpsvd`、`udpsvd` 等；扩充压缩解包、挂载、账号、文本和编辑器功能，开启 `FEATURE_SYSLOG_INFO` 修正正常信息日志级别。 | 两份自定义 BusyBox 配置均生效 | [configs/](configs/) |
| 证书 / 脚本运行环境 | 增加 ACME 及脚本依赖 | 选中 ACME、DNS API 脚本及 LuCI，QuickJS，以及 Lua argparse/cjson/curl-v3/FFI。 | 两份配置均选中 | [configs/](configs/) |
| CI / 平台选择 | 按需选择平台与恢复镜像 | AN7581、AN7583 可分别勾选，至少选一个；仅在勾选 recovery 时编译 `recovery.itb`。 | 默认 AN7581 开、AN7583 关、recovery 关 | [发布流程](.github/workflows/release.yml) |
| CI / Staging 缓存 | 构建并复用本仓库工具链 | 对主机工具、交叉工具链、Go/Rust 缓存计算指纹并校验；优先从 Actions、其次从 Release 恢复，未命中时重建，每个平台保留最新一份，不缓存目标产物或签名密钥。 | 默认 `use_staging_cache=true` | [缓存说明](docs/staging-cache.md)、[缓存脚本](scripts/staging-cache.py)、[测试](scripts/tests/test_staging_cache.py) |
| CI / 预编译软件包 | 在组装镜像前安装 APK | 从 `altman08/ponwrt` 的 `prebuild-package` Release 下载 APK，拒绝与本地已编译包重名，通过 `PREBUILT_APK_PACKAGES` 装入 rootfs；该安装路径允许未受信任的 APK。 | 发布流程启用；普通本地 `make` 不自动下载这些 APK | [发布流程](.github/workflows/release.yml)、[package/Makefile](package/Makefile) |
| CI / 构建诊断 | 共用依赖脚本并保留错误信息 | 统一依赖安装脚本，失败阶段用 `-j1 V=s` 重跑输出详细日志，上传失败日志，按平台收集镜像并生成发布校验和。 | GitHub Actions 发布构建 | [依赖脚本](scripts/ci-build-dependencies.sh)、[发布流程](.github/workflows/release.yml) |
| 构建系统 / 工作区 | 支持 feed 根目录软件包及本地目录 | 扫描软件包时规范根目录 Makefile 路径；忽略本地 `feed/` 检出目录和 `.staging-cache/` 归档。 | 构建元数据和开发工作区 | [include/scan.mk](include/scan.mk)、[.gitignore](.gitignore) |

表中的“选中”表示编译/安装配置，不表示所有服务默认开机运行。自定义 feeds 的实现由各自仓库维护，更新 feeds 后内容可能变化；主仓库不跟踪本地 `feed/` 检出目录。

Passwall 目前仍显示完整 Xray 的功能选项，尚未实现按精简版能力隐藏界面及过滤订阅。使用精简版时需要选择兼容的节点和 DNS 设置，不支持的配置可能导致启动失败。外部 DNS、基于防火墙的分流、SOCKS HTTP 回退、VLESS 反向代理与已移除的 Xray 功能需要分别看待。精简开发中测得的 ARM64 静态二进制约 14.81 MiB 仅为参考，不代表固定的 OpenWrt 包体积，工具链和构建参数会影响结果。

## ⚠️ 免责声明

PonWrt 是一个用于研究和开发的开源光猫固件项目。

刷写固件或修改 PON 相关配置存在风险，可能导致设备无法启动、配置或设备数据丢失、PON 无法注册等问题。操作前请务必备份原厂固件及设备相关数据。

使用者应自行确保相关操作符合当地法律法规及运营商相关规定。请勿将本项目用于未经授权的网络接入、冒用或复制他人设备身份，或干扰运营商网络正常运行。

因刷写、配置或使用本项目产生的设备故障、网络服务异常及其他后果，由使用者自行承担。

## 支持设备

| SoC | 设备 | Profile | 原厂校准/身份数据分区 |
| --- | --- | --- | --- |
| AN7581 | FiberHome HG5382A | `fiberhome_hg5382a` | `factory` |
| AN7581 | FiberHome HG5585F CT | `fiberhome_hg5585f-ct` | `factory` |
| AN7581 | FiberHome HG5585F CU | `fiberhome_hg5585f-cu` | `factory` |
| AN7581 | Gemtek XG2010G | `gemtek_xg2010g` | `dsd` |
| AN7581 | Nokia XG-040G-MD UBI | `nokia_xg-040g-md-ubi` | `bosa`、`ri` |
| AN7581 | Nokia XG-040G-TF UBI | `nokia_xg-040g-tf-ubi` | `bosa`、`ri` |
| AN7581 | UnionMan UNG00A | `unionman_ung00a` | `reservearea` |
| AN7581 | ZNXT ZN504XG-D | `znxt_zn504xg-d` | `reservearea` |
| AN7581 | ZNXT ZN515XG-D | `znxt_zn515xg-d` | `reservearea` |
| AN7583 | Nokia XG-040G-MF | `nokia_xg-040g-mf`、`nokia_xg-040g-mf-ubi` | `bosa`、`ri` |

## 编译

```sh
#  安装编译所需的工具链和库
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

#  或者使用ImmortalWrt一键脚本安装依赖
sudo bash -c 'bash <(curl -s https://build-scripts.immortalwrt.org/init_build_environment.sh)'

#  拉取源码
git clone -b dev https://github.com/altman08/ponwrt.git
cd ponwrt

#  更新并安装 feeds（软件包源）
./scripts/feeds update -a
./scripts/feeds install -a

#  选择配置 以目标7581为例
cp configs/an7581.config .config
#  若目标是 AN7583，改用下面这行：
cp configs/an7583.config .config


#  开始编译
# -j$(nproc) 表示用所有 CPU 核心并行编译，加快速度
make defconfig
make -j$(nproc)
```

固件位于 `bin/targets/airoha/an7581/` 或 `bin/targets/airoha/an7583/`。

GitHub Actions 的 **Release PonWrt** 可分别勾选 `an7581` 和 `an7583`，默认只选 `an7581`，至少需要选择一个芯片。`recovery` 默认不勾选，此时关闭 initramfs 编译，不生成 `recovery.itb`；勾选后同时编译 recovery 和 sysupgrade 固件。

GitHub Actions 的 **Release PonWrt** 默认开启 `use_staging_cache`，未命中时自动构建并保存本仓库自己的工具链和 Go/Rust 缓存，每个平台只保留最新一份。开启、更新和关闭步骤见 [Staging 缓存说明](docs/staging-cache.md)。

## 刷入

使用 [AN758x-Stock2UBI](https://github.com/pbs05/an758x-stock2ubi) 备份原厂闪存并安装 UBI 布局。启动镜像和 Web 恢复界面由 [AN758x U-Boot](https://github.com/pbs05/uboot-an758x) 提供。

刷入 PonWrt 后，通过 U-Boot Web 或 LuCI 的“网络 → PON → 配置 → PON board data”恢复原厂校准和身份数据。烽火 `factory` 需要先使用 [FiberHome Factory](https://github.com/pbs05/fiberhome-factory) 转换；转换后的烽火数据、`reservearea` 和 `dsd` 写入 PonWrt 的 `factory` 卷；Nokia 的 `bosa` 和 `ri` 写入同名卷。
