# C/S 无源码 UKey 接入调研

调研日期：2026-11-02。适用背景：多行业 C/S 业务系统、不修改业务源码；UKey 型号、目标程序和现网方案尚未确定。

## 研究状态与证据边界

2026-11-03 范围纠正：用户提出 REA，是希望分析第三方现有 UKey 接入软件，了解其实现机制；不是要求逆向用户自己的业务客户端。本文保留为第一轮公开文档调研，下面原有业务客户端验证计划不代表当前逆向任务。已经实施的第三方软件静态分析另见 [第三方 UKey 接入软件分析记录](third-party-ukey-reverse-analysis-2026-11-03.md)。

本次阅读了用户提供的 [REA reverse-engineer-anything SKILL.md](https://github.com/morluto/rea/blob/main/.agents/skills/reverse-engineer-anything/SKILL.md)，按“明确问题、选择证据、区分观察与推断、记录未知项”的方法整理资料。

本次执行的是公开资料研究。没有安装 REA、修改 MCP 配置、运行目标业务软件、附加进程或抓取现网流量；没有生成 REA Evidence。下文资料编号是文档索引，不是 REA Evidence ID。未取得任何目标客户的完整验收或密评报告，厂家文档不构成对本项目的合规结论。

## 公开资料支持的接入方式

| 方式 | 一手证据 | 可确认的机制 | 当前项目的适用边界 |
| --- | --- | --- | --- |
| 安全接入客户端＋网关 | D01、D02 | 终端组件承接业务流量，网关认证、授权并建立受保护通道；业务登录适配另行提供 | 需测试协议、流量覆盖和绕行路径；通道认证不能单独证明业务账号关联 |
| 桌面 ESSO / 控件代填 | D03、D04 | 识别登录窗体和字段，按模板或脚本输入业务凭据；部分历史实现有 Hook | 通常按应用适配；需处理凭据托管、失败检测、改密及版本变化 |
| 协议解析与账号绑定 | D05 | 通过已有 SSO 或识别登录报文，把接入账号与应用账号关联 | 依赖支持的协议及可见字段；私有加密协议等需重新验证 |
| 远程应用发布 | D03、D06 | 将原 C/S 客户端运行在受控服务器，通过远程会话访问，并代填及审计 | 运行位置改变；需验证外设、打印、文件、并发、授权及操作体验 |
| 复用已有认证协议或启动参数 | D07 | 本地 Agent 唤醒程序，并传递 OIDC 身份参数 | 文档要求应用能够解析该参数；原应用无此能力时，不能据此实现无源码接入 |

### D01：信安世纪 AG，流量接入与应用代填分别实现

[AG 安全接入网关产品白皮书](https://www.infosec.com.cn/ueditor/php/upload/file/20250518/1747556892305802.pdf)，封面为 2024 年 4 月，不能按上传目录标成 2025 版。

印刷页 4 描述 iSecSP 发起连接、网关创建国密 VPN 并处理认证授权；页 6 将 TCP/UDP 的 C/S 资源列入三层代理；页 7 单列 APP 代填。其四层代理条目仅明确 Web/B/S，不能扩大解释为支持任意原生 C/S。资料类型：厂家白皮书及功能说明，尚无本项目实测。

### D02：NetIAG，串行和旁路的保护范围不同

[信安世纪 NetIAG 官方说明](https://www.infosec.com.cn/default/index/product_detial/71)分别描述流量经过网关的串行部署，以及认证后业务交互不经网关的旁路部署。设计推断：选型时必须分别核实认证路径与业务流量路径，不能仅凭“已接入网关”认定通信保护完整。该页属于产品说明，具体实现仍需操作文档和测试佐证。

### D03：新华三，明确区分框体代填和命令行代填

[H3C SecPath A2000 应用发布配置指导，E6701 / 5W107](https://www.h3c.com/cn/Service/Document_Software/Document_Center/Home/Security/00-Public/Configure/Operation_Manual/H3C_SecPath_A2000_CN_CG_E6701-11306/)，第 5.3 节说明 AppAuto 录制 JSON 脚本，按脚本区分框体及命令行代填，并与远程客户端关联。它是在应用发布服务器上的实施，不能直接称为用户本机 ESSO。

### D04：Oracle、IBM 的历史 ESSO 实现

[Oracle Logon Manager 管理手册](https://docs.oracle.com/cd/E52734_01/esso/SSOAG/logon_manager.htm)列出 Control IDs、SendKeys、Journal Hook 等字段交互方式；[IBM SAM ESSO 8.2 安装参数](https://www.ibm.com/docs/en/samfess/8.2.0?topic=pcs-response-file-parameters-setuphlpini)列出默认关闭的 Console Hook Loader。

这些历史资料证明部分 ESSO 使用控件、事件和 Hook 完成适配，不证明当前国密厂商普遍采用相同实现，也不证明修改业务认证判断。微软现行 [SetWindowsHookExW 文档](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowshookexw)明确 Windows 11 起不支持 Journaling Hooks。旧实现需要重新验证平台兼容性。

### D05：深信服旧版手册中的主从账号绑定

[SANGFOR SSL VPN 6.6 官方手册](https://www.sangfor.com/download/product/helpdoc/SSLM66.pdf)，印刷页 187–188，描述结合 SSO 或解析登录报文中的用户名进行绑定，并配置应用类型及报文信息。该资料年代较早，仅作为机制先例；目标型号当前支持哪些协议、如何处理应用层加密，仍未知。PDF 全文访问超时，相关段落由公开搜索索引核对，未完成全文及截图检查。

### D06：华为云 CBH 的应用发布

[华为云 CBH 纳管应用资源](https://support.huaweicloud.com/usermanual-cbh/cbh_02_0019.html)说明在远程桌面服务器上部署客户端、纳管应用账户并代填及记录会话。它是运维应用发布实例，可以借鉴受控运行的思路；不能据此保证普通业务系统的外设和大规模并发体验。

### D07：启动参数接入具有应用能力前提

[阿里云 IDaaS 单点登录配置指南](https://static-aliyun-doc.oss-cn-hangzhou.aliyuncs.com/download%2Fpdf%2F160424%2F%25E5%258D%2595%25E7%2582%25B9%25E7%2599%25BB%25E5%25BD%2595%25E9%2585%258D%25E7%25BD%25AE_intl_zh-CN.pdf)，文档版本 20220322、第 28 页，描述 IDP-Agent 唤醒程序并传递 OIDC 参数，并明确要求应用接收及解析该参数。属于历史接入例证，不作为当前产品支持承诺。

## 原拟业务客户端分析计划（当前逆向任务不采用）

以下是后续对指定测试样本的分析计划，并非已执行结果。Windows 工具为示例；其他平台需选择对应工具。

| 问题 | 分析与证据 | 对接入选择的作用 |
| --- | --- | --- |
| 客户端属于什么技术栈？ | 提供安装目录后，按 REA 的桌面目录检查路线识别运行时，再选择 .NET、Electron 或原生分析 | 避免直接对全部 EXE 做深度反编译 |
| 原有登录能力是什么？ | 检查启动参数、配置、相关模块及登录调用关系 | 判断可否复用已有身份接口或参数 |
| 窗体能否可靠操作？ | 用 UI Automation 工具确认输入框、按钮与状态；测试正常及失败路径 | 判断是否适合界面适配；按应用及版本保存模板 |
| 实际访问哪些服务？ | 关联进程与端点、记录登录及业务操作中的连接，必要时分析已保存抓包 | 确定资源、协议与流量保护范围 |
| 业务身份在哪里确定？ | 关联客户端输入、认证响应和服务端会话；用受控测试核实 | 判断能否有效绑定证书身份与业务账号 |
| 升级后适配是否有效？ | 记录样本哈希、版本和分析范围，比较新旧构建并重验关键流程 | 决定维护成本和支持矩阵 |

工具能力依据：[REA 桌面检查](https://github.com/morluto/rea/blob/main/docs/desktop-applications.md)、[REA .NET 静态检查](https://github.com/morluto/rea/blob/main/docs/managed-code-analysis.md)、[微软 Inspect](https://learn.microsoft.com/en-us/windows/win32/winauto/inspect-objects/)、[Process Monitor](https://learn.microsoft.com/en-us/sysinternals/downloads/procmon)、[TCPView](https://learn.microsoft.com/en-us/sysinternals/downloads/tcpview)、[Wireshark 文档](https://www.wireshark.org/docs/wsug_html_chunked/ChapterIntroduction.html)。

能力限制：静态导入或字符串只能作为线索，不能证明调用已发生；端点列表不能证明业务账号；加密抓包不自动揭示认证内容；界面代填成功不能证明无法手动换号或绕行。REA 原生动态工作流的主机支持各不相同，不能假定 macOS 上可直接运行目标 Windows 客户端。

## 建议的接入设计

工程建议：将可复用能力与应用适配分开，认证、凭据及令牌管理、流量保护和审计分别定义接口；每个应用记录协议、账号绑定方式、可控入口和版本支持情况。

```text
UKey ── 设备接口适配 ── 认证与授权
                            │
                 具体业务应用的接入配置
                   ├─ 已有认证接口或参数
                   ├─ 界面 / 命令行适配
                   ├─ 受支持的协议解析
                   └─ 远程应用发布

原业务流量 ── 安全接入组件 ── 受保护通道 / 网关 ── 业务端
```

该图是建议架构，具体应用不需要同时采用全部分支。应优先验证已有接口；无现成接口时评估界面或协议适配；运行位置允许改变时再评估应用发布。只有实际问题需要时，才进一步分析代码或进行受控运行观测。修改 EXE、替换认证库或更改运行时判断，需要单独确认授权与约束，不能从“不改源码”推导出已允许这些变更。

对商用密码改造，仍需分别证明产品使用条件、证书与密钥管理、身份与业务会话关联、访问不可绕过以及实际通信保护范围。公开案例和逆向结果只提供技术证据，系统结论需按适用要求评估。[密评管理办法](https://oscca.gov.cn/sca/xxgk/2023-10/07/content_1061109.shtml)

## 结论及尚未解决的问题

已回答：公开资料确有安全客户端＋网关、ESSO 代填、协议绑定、应用发布及已有协议参数等路线；部分历史 ESSO 有 Hook 机制。

部分回答：已找到厂商操作说明和机制先例，但各路线与商密认证的组合方式，需要具体产品及系统验证。

未解决：目标程序与版本、UKey 型号及证书用途、现有密码设施、终端和网络变更条件、业务账号绑定的可实施性，以及系统适用密改指标。未取得这些证据前，不对某一产品或通用适配器作全覆盖承诺。

当前逆向任务：先分析公开发行的第三方安全接入软件及 UKey 中间件，查明设备接口、认证调用、组件分工及会话关联机制。用户业务客户端的现场适配验证属于之后的实施工作，不能拿它代替对已有软件实现的研究。
