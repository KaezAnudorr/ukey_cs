# 文档导航

了解如何构建运行，先读[产品说明](../product/README.md)；了解接入方案，先读[设计草案](design/cs-ukey-access-design-v0.1.md)，再看[交付计划](delivery/cs-ukey-pilot-delivery-plan-v0.1.md)和[验收矩阵](delivery/cs-ukey-pilot-acceptance-v0.1.md)。

## 需求、设计与交付

| 文档 | 内容 |
|---|---|
| [访谈与资料收集清单](intake/teacher-interview-web-ukey-to-cs-2026-11-04.md) | 目标系统、终端、设备及接入约束 |
| [C/S 接入设计草案](design/cs-ukey-access-design-v0.1.md) | 候选架构、身份关联和业务适配路线 |
| [交付与实施计划](delivery/cs-ukey-pilot-delivery-plan-v0.1.md) | 首版范围、工程组织、交付部件和推进条件 |
| [验收矩阵](delivery/cs-ukey-pilot-acceptance-v0.1.md) | 试点验收项、方法及待验证边界 |
| [产品架构](../product/ARCHITECTURE.md) | 当前 DEMO 的技术边界 |
| [来源与迁移关系](../product/PROVENANCE.md) | 旧网页方案与新 C/S 工程的关系 |
| [测试说明](../product/TESTING.md) | 自动测试、进程验证与结果解读 |
| [交接包制作说明](../handoff/README.md) | 打包所需文件与接收方入口 |

## 调研与原有网页插件

| 文档 | 内容 |
|---|---|
| [C/S 无源码接入调研](research/cs-ukey-integration-research-2026-11-02.md) | 公开产品方案和可采用的接入方式 |
| [第三方 UKey 软件静态分析](research/third-party-ukey-reverse-analysis-2026-11-03.md) | 已分析样本的驱动、中间件和认证机制 |
| [网页 JS 静态分析](research/main-interceptor-all-analysis-2026-11-05.md) | 登录拦截、接口调用和已发现问题 |
| [部署手册与 JS 对照分析](research/login-security-plugin-deployment-cross-analysis-2026-11-05.md) | 网页插件的两种部署方式及职责 |
| [原插件服务端源码分析](research/ymnmr-source-analysis-2026-11-05.md) | `ym-login-plug:1.1.5` 的代理和认证流程 |
| [登录安全性插件拦截架构](research/登录安全性插件拦截架构.md) | 从本地工作目录归入的原有架构图与时序说明 |

研究报告保留其原分析日期、样本版本和结论；工作目录中的现有 JAR、JS 并未据此认定为报告中的同一份样本。

## 未随仓库提供的材料

2026-11-10 拉取的上游提交 `44bfca7` 未包含下列材料。历史报告中的 `/Users/chen/project/cs-ukey/...` 是原作者机器路径；指向仓库现有文档的链接已改为相对路径，缺失材料的原始引用保留以便追溯。

| 路径 | 缺少的内容及影响 |
|---|---|
| `docs/validation/` | 网页验证、C/S 开发、增强验证和三网区实验的历史报告，当前无法查阅原记录 |
| `artifacts/` | 旧插件完整源码 ZIP、部署 PDF 和第三方软件等原始样本；该目录被 Git 忽略 |
| `evidence/` | 样本清单、检查记录和历史验证 JSON；该目录被 Git 忽略 |
| `validation/web-ukey-local/` | 原网页验证脚本及其工具链记录；本次拉取后不能直接执行网页验证 |
| `product/dist/` | 预构建源码包和二进制包；需要按产品说明自行构建、打包 |
| `product/.runtime/` | 机器本地的演示证书和配置；由 `demo-init` 生成 |

制作完整交接包还需要两份原始基线结果：`evidence/development/2026-11-06/v0.2/acceptance-result.json` 和 `evidence/development/2026-11-09/network-lab/network-result.json`。补齐方式见[交接包制作说明](../handoff/README.md)。
