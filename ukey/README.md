# C/S UKey 安全接入试点

本仓库提供 C/S 安全接入 DEMO 的源码、设计调研、交付计划和网络实验工具。开发从 [product/README.md](product/README.md) 开始；查阅方案从[文档导航](docs/README.md)开始。

目标是在不修改原业务程序源码的前提下，交付可按手册部署、可在隔离仿真生产环境使用真实 UKey 验证指定 C/S 系统的工程。首版范围是一个明确的 C/S 系统版本、一款 UKey，以及明确的终端、服务端和密码组件组合；具体系统与设备尚待选定。

## 目录

```text
ukey/
├── product/                 C/S DEMO Maven 工程
│   ├── common/              公共配置、TLS、协议与审计
│   ├── access-server/       认证、授权会话与接入转发
│   ├── desktop-agent/       桌面接入 Agent
│   ├── lab/                 样例业务服务、客户端与探针
│   ├── config/              真实试点配置模板
│   └── tools/               构建、运行、验证、打包与配置导入
├── docs/                    需求、设计、研究和交付文档
├── handoff/                 交接包制作工具和使用说明
└── lab/network/             Debian 隔离网络实验
```

`product/lab/` 是 Java 样例业务模块；`lab/network/` 是网络实验工具，两者分别保留原有构建和运行路径。

## 构建与运行

准备 JDK 17+（含 `keytool`）、Python 3.10+、Maven 3.9+，设置 `JAVA_HOME` 并把工具加入 `PATH`。在本仓库根目录执行：

```powershell
python product/tools/manage.py build
python product/tools/manage.py demo-init
python product/tools/manage.py smoke
```

macOS/Linux 将 `python` 换为 `python3`。首次构建需要获取 Maven 依赖；`demo-init` 在 `product/.runtime/demo/` 创建演示证书和配置，已有非空目录不会覆盖。`smoke` 成功时输出 `Native C/S flow completed without browser`。桌面窗口、打包和配置导入见[产品说明](product/README.md)，增强验证见 [TESTING.md](product/TESTING.md)。

当前产品版本为 **0.2.0-demo**，使用软件证书和标准 TLS 1.3，仅支持 DEMO。真实 UKey、SKF、SM2、TLCP 和现场业务适配尚未完成；REAL-PILOT 会拒绝启动。具体保护范围与已知缺口见[架构说明](product/ARCHITECTURE.md)和[验收矩阵](docs/delivery/cs-ukey-pilot-acceptance-v0.1.md)。

## 交付与网络实验

- [交接包制作入口](handoff/README.md)：区分源码中的模板与已制作的交付 ZIP。
- [首版交付与实施计划](docs/delivery/cs-ukey-pilot-delivery-plan-v0.1.md)：服务端与终端分别构建交付的安排。
- [隔离网络实验](lab/network/README.md)：Debian 三网区实验及 Apple Silicon Mac 启动工具。

## 历史验证记录与本次拉取范围

上游首页记录了以下历史结果，所引用的报告和原始证据未随当前 Git 提交提供。这些数字属于上游历史记录；在本机运行后的结果应以本次生成的报告为准。

| 上游记录的验证 | 历史结果 | 引用的报告（未收录） |
|---|---|---|
| 网页插件本地验证，使用模拟助手和密码服务 | 14 项预定观察，包含已复现的安全及功能问题 | `docs/validation/web-ukey-local-validation-2026-11-06.md` |
| C/S DEMO 开发与增强验证 | 37 项自动测试；独立进程检查 15 项符合预期、2 项隔离缺口，含 60 秒双身份/6 连接负载、二进制、半关闭、200 次建连及崩溃恢复 | `docs/validation/cs-demo-development-2026-11-06.md`、`docs/validation/cs-enhanced-validation-2026-11-06.md` |
| 源码包与二进制包交付复测 | 在含中文和空格的新目录构建与运行 | `docs/validation/cs-enhanced-validation-2026-11-06.md` |
| Debian 三网区实验 | 9 项检查通过，覆盖 IPv4 原业务端口阻断、弱网传输与链路恢复 | `docs/validation/cs-network-lab-2026-11-09.md` |

上游网页验证入口 `validation/web-ukey-local/bootstrap.py`、`run-validation.cjs` 也未收录，不能在刚拉取的目录直接执行。上游记录尚未完成 Windows/Linux 实机、真实网络隔离和原业务系统验收；上述 Debian 结果属于虚拟机实验。

原始材料 `artifacts/`、证据 `evidence/`、网页验证 `validation/`、临时文件 `tmp/`、构建输出 `**/target/`、运行目录 `product/.runtime/` 和发行目录 `product/dist/` 已由 `.gitignore` 排除。所缺文件及交接包依赖见[资料缺口](docs/README.md#未随仓库提供的材料)。
