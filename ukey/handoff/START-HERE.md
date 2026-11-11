# C/S UKey 0.2.0 交接测试

解压整个 ZIP，打开这个目录。开发侧交付本地复测版本、源码和报告。公司已有模拟生产测试平台，由有权限的接收方在指定测试区执行部署和验证。平台上的执行顺序和回传内容见 [公司环境试点记录](REAL-PILOT.md)。交接范围是 C/S，原网页端沿用现场已有流程。

| 要验证什么 | 环境 | 入口 |
|---|---|---|
| 本机功能和进程故障 | Windows、macOS 或 Linux，准备 Python 3.10+ 和带 `keytool` 的 Java 17+ | 本目录 `test.py` |
| 网络隔离、丢包和恢复 | 公司测试平台的指定测试区。随包也提供已验证的 Debian 实验作为复现参考 | [网络实验](NETWORK.md) |
| 指定业务、实体 UKey 和密码组件 | 公司授权的模拟生产区，准备目标客户端、服务端、终端系统、UKey、驱动或助手、证书和选定的密码产品 | [公司环境试点记录](REAL-PILOT.md) |

本机测试使用随包 JAR，无需 Maven 或网络下载。以下是 Windows 的命令行入口。

```bat
.\test.cmd doctor
.\test.cmd quick
```

macOS 和 Linux 使用以下命令。

```sh
python3 test.py doctor
python3 test.py quick
```

`doctor` 核对包内 SHA-256、Python 和 Java。已有多个 JDK 时，用 `--java-home` 指定本次使用的 JDK 目录。命令的 `quick` 与 `full` 都执行现有独立进程用例，持续负载阶段分别为 5 秒和 60 秒。工具自动选择回环端口，每次在 `results/` 下创建新目录和演示证书。默认目录无法写入时，使用 `--output` 指定一个可写目录。

公司环境为麒麟 x86 时，先确认实际架构和系统版本，并区分它承担的是服务端、终端还是两者。当前 JAR 为 Java 17 字节码，目标机器使用匹配架构的运行时。麒麟实测状态和首轮命令见 [麒麟环境检查](REAL-PILOT.md#麒麟-x86-首轮检查)。

运行结束后回传 `results/<本次目录>/acceptance-result.json`。若启动失败，记录控制台错误及发生在哪一步。整个运行目录包含演示私钥与口令，回传前按文件选择所需报告和日志。报告中 `OBSERVED_GAP` 是已确认的隔离缺口，`FAIL` 是测试失败。两者应分别记录，`production_ready` 始终为 `false`。

源码在 `source/cs-ukey-pilot-0.2.0-demo-source.zip`。解压后按其中 README 构建，另需 Maven 3.9+ 及可访问的依赖仓库或已准备好的构建缓存。日常本机验证可以一直使用 `demo/` 的现成 JAR。

历史实测报告位于 `baseline/`。交接脚本已在 Apple Silicon Mac 和 Debian arm64 上复测，Debian 也通过了三网区实验。接收方在公司指定环境重新执行并记录版本和结果。Windows 原生环境、真实业务和真实 UKey 兼容性仍需实测。
