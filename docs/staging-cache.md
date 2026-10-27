# 构建和使用自己的 Staging 缓存

缓存由本仓库的源码、feeds 和配置构建，不下载其他仓库的构建缓存。普通发布流程自动维护缓存，AN7581 和 AN7583 各保留最新一份。

## 首次开启

1. 将更新后的 `.github/workflows/release.yml`、配套脚本以及删除独立 `warm-cache.yml` 工作流的改动提交并推送到 GitHub。
2. 打开 **Actions → Release PonWrt → Run workflow**，选择源码分支，填写发布标签，保持 `use_staging_cache` 勾选（默认开启）。签名密钥仍按正常固件发布配置。
3. 首次运行或指纹变化时，流程先构建主机工具、交叉工具链及 Go/Rust 主机工具，校验后保存缓存，再继续编译固件。首次运行不会因为缓存加速；后续兼容构建可以复用。
4. 在任务摘要中查看 `Restored: true (actions)` 或 `Restored: true (release)`；新建缓存时显示 `Rebuilt: true`，Release 备份可用时显示 `Release backup available: true`。
5. **Releases → Staging Build Cache** 会自动出现 AN7581、AN7583 各自的 `.tar.zst` 和 `.json` 文件。该 Release 标记为预发布，不会替代最新正式固件。

无需为缓存额外添加 PAT 或 Secret。发布构建使用内置 `GITHUB_TOKEN`，声明 `contents: write` 用于 Release 备份、`actions: write` 用于清理旧缓存；仓库或组织策略需允许这些权限。

## 更新、重建和关闭

- 每次发布在拉取 feeds、生成最终配置后重新计算指纹。工具链、主机构建定义、相关配置或主机环境变化导致未命中时，会自动构建并保存新缓存，无需判断后手动更新。
- feeds 中纯目标软件包的更新不会使整份主机工具缓存失效；正常编译会构建更新后的包。Go/Rust、其他 HostBuild 包或共用主机构建规则更新则会改变 key，自动生成新缓存。
- 缓存缺失、损坏或工具运行检查失败时，任务摘要显示 `Restored: false (none)`，随后尝试构建并保存新缓存。缓存预构建或上传、清理失败不会阻断后续固件编译，可在对应步骤日志中查看原因。
- 临时关闭：运行 **Release PonWrt** 时取消 `use_staging_cache`。
- 切换分支时不需要单独预热。跨分支 Actions 缓存受 GitHub 作用域限制，但相同指纹的 Release 备份仍可使用；不兼容则自动重新构建。

## 仅保留最新缓存

Actions 缓存和 `staging-cache` Release 备份均按 SoC 清理：AN7581、AN7583 各只保留最新的一份，Release 中一个归档和对应 JSON 元数据算同一份。两个平台的工具链不能共用，因此构建两个平台时会保留两份缓存。

新缓存保存成功后才删除该平台旧指纹、旧运行的缓存，保留另一个平台及 `ponwrt-dl-*` 源码下载缓存。命中已有缓存时也会清理历史版本；Release 备份内容相同时跳过重复上传。相同 SoC 的构建会排队执行，避免上传和清理相互覆盖。

如果上传失败、Actions 新快照暂未可见，或清理接口失败，会保留旧缓存并在后续发布时再次尝试清理。旧源码对应的缓存被替换后，再构建旧源码会自动重新生成，不会恢复不兼容的新缓存。

## 缓存范围和一致性

保存 `staging_dir/host`、`hostpkg`、`toolchain-*`、`target-*/host`，以及主机包的 `.prepared*`、`.configured*`、`.built` 标记。内核、目标应用构建目录、根文件系统、签名密钥均不在缓存中。

key 包含构建路径、主机系统/架构/编译器、缓存脚本版本、构建系统源文件和补丁、已安装的 HostBuild 包定义及源码、Go/Rust 共用定义、feeds 配置和工具链相关的最终配置。纯目标软件包的源码变化不直接改变 key；若它带来新的主机构建依赖，对应 HostBuild 输入会影响 key。

OpenWrt 的部分 `.prepared` 名称依赖源码 mtime，因此脚本统一主机构建输入的 mtime，恢复后刷新真实的 OpenWrt stamp。归档通过 SHA-256、指纹、构建路径和内容范围检查后才解压，并验证 Go/Rust/Cargo 可运行、交叉 GCC 可链接程序。工具校验失败时清除已恢复的工具及标记，防止错误跳过重建。

缓存生成与固件编译在同一个 Ubuntu 24.04 任务、同一个仓库工作目录中完成。缓存使用固定的 `staging-cache` Release 作长期备份，优先从 Actions 恢复，缺失时从本仓库 Release 恢复。

## 本地验证

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/tests/test_staging_cache.py
```

测试使用临时目录和小型工具替身，覆盖指纹失效、源码时间一致性、归档往返、目标产物排除、损坏回退、失败清理，以及先保存后清理和平台间隔离；不执行固件编译或真实 GitHub 写入。
