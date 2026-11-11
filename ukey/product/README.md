# C/S UKey Pilot 0.2.0-demo

这是新增的可运行 C/S 接入演示工程。它包含服务端、桌面接入 Agent、独立 C/S 业务客户端和业务服务。运行时仅依赖 JDK 17+ 标准库；无需浏览器、Node、云密助手或闭源密码 SDK。

**当前版本只支持 DEMO。** 使用运行时生成的软件证书和标准 TLS 1.3 双向认证，不使用真实 UKey、SKF、SM2、TLCP 或商密产品。REAL-PILOT 会在绑定端口前明确拒绝启动，不会悄悄切换为软件身份。

## 快速运行：源码包

前提：JDK 17+、Python 3.10+、Maven 3.9+，设置 `JAVA_HOME` 并能执行 `java`、`keytool`、`python3`（Windows 为 `python`）和 `mvn`。

```sh
python3 tools/manage.py build
python3 tools/manage.py demo-init
python3 tools/manage.py smoke
```

Windows PowerShell 把上面的 `python3` 换成 `python`。第一次 `build` 从 Maven 仓库获取构建/测试依赖；二进制包运行不需要 Maven。

`demo-init` 在 `.runtime/demo` 中生成本次演示的 CA、服务端和客户端证书、随机口令及相对路径配置。已有目录不覆盖，不把私钥和口令写入源代码或发行包。

`smoke` 启动三个独立 Java 进程（业务服务、接入服务、Agent），再运行独立 C/S 客户端。预期输出包含：

```text
OK alice
USER alice
Native C/S flow completed without browser
```

完成后自动停止本次启动的进程，结果写入 `.runtime/demo/smoke-result.json`。遇到已占用端口会停止，不结束别人的进程。

## 增强验证：并发、故障和已知缺口

```sh
python3 tools/manage.py acceptance --seconds 60
```

自动生成新测试目录和证书，使用独立进程完成二进制/UTF-8/半关闭传输、两个身份 6 条长连接持续负载、200 次连接循环、进程强制结束/重启、退出撤销和过期检查，输出 JSON 报告。源码构建还执行 37 项 JUnit 测试。

原业务端口直连、同机其他进程使用已授权 Agent 端口会记为 `OBSERVED_GAP`。报告始终标识 `production_ready=false`，不会把检查完成当成防绕行或真实商密验收通过。详见[增强验证说明](TESTING.md)。

## 手工体验桌面窗口

先在不同终端启动：

```sh
python3 tools/manage.py business
python3 tools/manage.py server
python3 tools/manage.py agent --gui
python3 tools/manage.py client --gui
```

在 Agent 窗口点击 `Connect DEMO`，然后在 C/S 样例窗口执行登录和业务请求。Agent `Disconnect` 会撤销会话并关闭本地端口和连接。关闭后台终端时用 Ctrl+C。

命令行 Agent 可在终端输入 `disconnect` 后回车，正常撤销会话并退出；不依赖不同操作系统的进程终止信号语义。

Agent 默认监听 `127.0.0.1:19500`；API 为 `https://localhost:19443`，TLS CONNECT 接入端口为 19444，样例业务服务为 `127.0.0.1:19510`。全部仅监听回环地址。

## 二进制包

源码构建通过后：

```sh
python3 tools/manage.py package
```

生成 `dist/cs-ukey-pilot-0.2.0-demo.zip` 和 SHA-256 文件。接收方解压后执行 `demo-init`、`smoke` 即可，不需要 Maven，也不需要修改源码。证书必须在接收方机器上重新生成。

包内 `SHA256SUMS.json` 记录每个交付文件的摘要。Windows 可使用 `tools/run.ps1`，macOS/Linux 可使用 `tools/run.sh`，也可以直接执行 Python 入口；不要求更改系统脚本执行策略。

## 已实现的保护

- API 和业务接入均要求 TLS 客户端证书，验证服务端主机名，不提供 HTTP 降级入口。
- 客户端证书指纹必须在配置中登记；设备序列号不作为认证凭据。
- 授权会话在服务端保存，绑定证书、身份、资源和有效期。
- 接入目标仅从服务端固定资源配置选择，客户端不能指定任意目标。
- 退出、过期后拒绝新连接，并关闭已登记的连接。
- 为内置样例协议提供业务账号检查：Alice 的接入身份不能使用 Bob 的业务账号。原业务密码仍由样例业务服务验证。
- 审计记录行为和身份，使用会话摘要，不记录原始会话凭据、业务密码或私钥。
- 原 `/verifySign` 等布尔认证接口在新服务中返回 410，不作为业务准入。

## 边界与真实接入缺口

1. 这不是已完成的商密或真实 UKey 版本。真实驱动、助手、密码服务、国密通道和生命周期适配尚未接入。
2. 业务账号检查器仅认识内置 UTF-8 行协议 `LOGIN 用户 密码`，不能用于任意医院或政务客户端。真实系统需要另一个经过验证的适配器。
3. 本机其他程序能够直接访问演示业务端口 19510。这是受控通路的功能演示，不是已经完成的网络防绕行部署。真实试点必须在隔离网络/服务器策略中限制原业务入口，并验证同机用户、进程和备用路径。
   已认证 Agent 的回环端口也没有 OS 用户/进程鉴别，同机其他进程可以借用该通道，但仍受已授权业务账号及业务密码检查约束。不能把监听回环地址当作用户或进程隔离。
4. TLS 只保护 Agent 到接入服务；样例客户端到 Agent、接入服务到样例业务均为本机 TCP。不能把它当作所有现场链路已经受到密码保护。
5. 吊销状态、实体设备拔出、真实 PIN 输入、Windows 驱动兼容、安装服务和生产运维能力均未验证。DEMO 没有真实 PIN 窗口。
6. 原 `ym-login-plug:1.1.5` 网页插件仍保留在原样材料中；本次没有宣称原网页入口已完成迁移。不能并行保留可绕过新入口的旧代理来宣称整体强制认证完成。

详见 [架构决策](ARCHITECTURE.md)、[来源与迁移说明](PROVENANCE.md)。真实试点需要填定 `config/pilot-support.template.properties` 所列的具体组合并实现验证过的适配器。

## 配置、诊断与导入

```sh
python3 tools/manage.py diagnose
python3 tools/import_legacy.py legacy-config.json --resource sample --output reviewed-identities.properties
python3 tools/manage.py server --config config/real-pilot.properties
```

导入工具只转换原配置中精确的业务账号/证书映射，不导入密码服务密钥或启动服务；非精确匹配规则拒绝自动转换。证书信任与用途仍须独立核实。最后一条命令应以退出码 2 拒绝，这是本版本的真实模式保护。
