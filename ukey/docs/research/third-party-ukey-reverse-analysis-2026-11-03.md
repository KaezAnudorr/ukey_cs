# 第三方 UKey 接入软件：第一轮静态逆向分析

分析日期：2026-11-03。研究目标：从实际发行的软件包查明别人如何接入 UKey，为网页与 C/S 接入设计提供实现证据。用户已澄清：其网页是否存在前置网关尚未知，本文不把第三方样本的架构视为用户现网事实。

## 执行范围与证据

已下载并静态拆解 iSecSP、EasyConnect 与 SHECA UniAgent 的发行包，使用 REA 6.8.0 执行 JavaScript 静态分析、ELF/PE 导出表检查和 PE 导入表检查，共保存 8 项成功结果。调用关系另以系统 LLVM objdump 的汇编、ELF 重定位表和文件位置核对。

没有运行这些软件、安装其驱动、连接第三方生产网关或使用真实 UKey。本文中的“调用”表示代码中存在相应调用路径，不表示已观察到运行。没有开展原生反编译器会话或完整运行时验证。

REA 通过独立命令行使用，没有注册 MCP 或修改 Codex 配置。常规依赖安装停在与本次静态工作无关的 Frida 安装步骤后已中止，随后以 npm 的 ignore-scripts 方式完成 CLI 获取；本次不宣称 Frida 或其他动态引擎可用。拆包使用官方 7-Zip 26.05 独立工具。没有执行目标安装器。

完整命令、REA Evidence ID、样本哈希和工具输出保存在 ../../evidence/third-party/2026-11-03/。REA 原始导入/导出事实与普通工具生成的汇编、字符串记录分别保存，不把后者称为 REA Evidence。

## 样本与来源

| 样本 | 来源及版本边界 | SHA-256 |
| --- | --- | --- |
| iSecSP Ubuntu 分发包，51,685,724 字节 | [北京大学公开软件分发页](https://its.pku.edu.cn/service_1_vpn.jsp)；文件名标注 2.4.7_31834，Debian control 为 2.4.7，包内 version 文件却为 client_version=2.4.0，三者分别记录，不合并为已验证的运行版本 | f9d6c1a79b2d924591f8c7a9df2082bc27eaffa5b7721e6e878db1bfb9995e9c |
| EasyConnect Windows 离线包，35,723,880 字节 | [官方社区发布帖](https://bbs.sangfor.com.cn/forum.php?mod=viewthread&tid=215425)链接至 download.sangfor.com.cn；文件名是 M7.6.7 及以上的兼容标签，外层 PE 资源版本为 7.6.7.0；HTTP Last-Modified 为 2020-12-02，按历史样本处理 | b1a681c1ad06e8e2179a540e77d02b9ec90bc2583a9298c17bb904b7166ffa0a |
| SHECA UniAgent ZIP，9,060,421 字节 | [上海 CA 官方下载页](https://www.sheca.com/resources/tools)；分发标签 3.0.3115.32，所含 UniAgent.exe 的版本字符串为 3.3.0.5；CDN Last-Modified 为 2017-06-19，按历史中间件样本处理 | 629247cd2172f7b514bc1228101ea4f1f7d0e6531d16bb040680db1575aa7519 |

另已下载 BJCA V3.3.05.1445，当前尚未深入分析，不计入下面的实现结论。HTTP 时间和内嵌版本只是各自的记录；没有验证代码签名、上游发布校验和或运行时构建。哈希用于固定本次分析的字节身份。

## A. iSecSP：SKF 驱动适配与通信库签名回调

核心对象为包内 opt/iSecSP/libvl3vpn.so，SHA-256 为 f03deec73155f7dd97adbac6513f90ec1c07cbc7d661c84355709e5d9a48405f。该 ELF 保留了符号，可以结合汇编及 GOT 重定位定位实际间接调用。

已确认的代码路径：

1. loadskfdriver（0xe2a6d）通过 dlopen 加载驱动；loadandsetgmfunc（0xe2cad）通过 dlsym 解析 SKF_ConnectDev、SKF_VerifyPIN、SKF_ECCSignData、SKF_ExportCertificate 等函数，并写入对应函数指针。
2. skf_open（0xdf7ae）顺序检查并调用连接设备、打开应用、校验用户 PIN、打开容器的指针；各步有返回值检查与失败清理。通过重定位可把间接调用对应到具体 SKF 名称，而不只是看到字符串。
3. ssl_connect_skf（0xeb81a）调用 ssl_connect_check_skf；后者包含加载驱动、skf_open 和 ukey_export 的调用。ukey_export 调用证书、公钥导出接口并初始化密钥方法。不能从这个函数名推断它在导出私钥。
4. init_gm_skf（0x10df61）将 ukey_sign（0x10d3ce）注册到 EVP_PKEY_meth_set_sign。ukey_sign 通过已解析的 SKF_ECCSignData 请求设备签名，再使用 BN_bin2bn、ECDSA_SIG_set0、i2d_ECDSA_SIG 整理签名格式。
5. ssl_connect_vpn_sm2（0xeca8e）直接调用 ssl_connect_skf；该路径中可见证书/密钥配置和 SSL_connect。代码支持“把设备签名衔接到所带通信库”的解释，实际协商算法、握手报文和网关验证策略尚未运行验证。

据此整理的机制为：接入客户端选择设备及证书 → SKF 驱动验证 PIN、打开容器 → 通信库需要签名时调用设备接口 → 继续网关连接。驱动查找函数也存在，说明设备适配有单独的加载边界；不代表任意品牌和型号均可直接兼容。

主要证据：isecsp-skf-callpaths-annotated.asm、isecsp-skf-loader-and-key-bridge.asm、isecsp-libvl3vpn-relocations.txt、两份 static/cert-bridge callsites JSON；导出身份由 R01 固定。汇编中的 GOT 注释依据同一文件的重定位表生成，原始汇编也保留。

## B. EasyConnect：界面调用本地 Agent，普通 Key 与国密 Key 分路

外层 EXE 的 PE 资源包含另一层安装器，继续拆解后可取得 EasyConnectUIInstaller、ECAgentInstaller、SangforCSClientInstaller，以及独立的网络和 SSO 组件。它们是软件包中的独立成员；本次未逐一验证网络或 SSO 功能。

对实际发行包中的 6 个 JavaScript 文件执行了 REA 静态分析，解析失败数为 0；其余 139 个已编目文件未纳入该次语义分析，整体图仍有显式未知项，不能把该结果当成完整程序证明。

已核对的实现细节：

| 位置 | 观察到的逻辑 | 能支持的结论 |
| --- | --- | --- |
| Web/jssdk/business/auth_key_cert.js | authKey 先取初始配置，再调用 SFAPI.loginKey，并传入 Key 类型和 PIN | 界面层提供统一的 Key 认证入口 |
| Web/jssdk/api/auth_key.js | 类型 2 选择 NdKeyAuth，类型 4 选择 GmKeyAuth；以 ECAgent 类型提交请求 | 普通 USBKey 和国密 Key 有不同的本地操作入口 |
| Web/jssdk/common/config.js | EC_URL_TEMPLATE 指向 https://127.0.0.1:{0}/ECAgent/；默认端口声明为 54530，也存在其他候选端口 | 这里配置的是本机组件入口，不能把此配置当成实际监听结果 |
| Web/jssdk/common/request.js | 把操作名、参数和 token 组装为本地组件请求；所检查的 ECAgent 路径最终使用 GET/兼容请求方式 | 上层指定 post 并不等于最终传输方法；PIN 在此链路中经过 Base64 编码，编码本身不构成加密 |
| SangforCSClientInstaller | 包含 USBKeyManager.dll、ShuttleCsp11_3000GM.dll；原生程序有 CGMDkey、SKF_VerifyPIN、DoDKeyAuth 的位置线索 | 原生组件中存在 Key/国密相关实现线索；字符串本身不证明运行时调用 |
| ShuttleCsp11_3000GM.dll 导出表 | 同时提供 SKF_ConnectDev、SKF_VerifyPIN、SKF_ECCSignData、C_GetFunctionList、C_Login、C_Sign 和 CSP 类接口 | 一个设备库可以暴露多套接口；具体分支采用哪套接口仍需追踪或运行观测 |

因此，已证实的上层结构是：界面 Key 认证逻辑 → 本机 ECAgent 请求接口。原生包具备与之相关的 Key 组件和设备接口，但本轮没有完整恢复 ECAgent 到 CGMDkey 的进程间分发及全部网关认证报文，图中的这段不应伪装成已完成运行验证。

[深信服官方故障案例](https://support.sangfor.com.cn/cases/read?category_id=4332&product_id=20)另行证明产品存在国密内置 CA 的 USBKey 认证场景；它是外部佐证，不替代对这个历史安装包、设备组合及实际部署的验证。

主要证据：R02、R03、R04、R05；easyconnect-auth-source-locations.json 保存原始文件哈希、行号和 UTF-8 字节位置；easyconnect-native-pe-inventory.json 保存普通静态工具的原生线索。

## C. SHECA UniAgent：证书中间件与多种设备后端

历史样本中，UniAgent.exe 的导入表明确引用 SafeEngine.dll 的 SEH_InitialSession、SEH_ClearSession、SEH_EncodePKCS12。SafeEngine.dll 导出表又提供 SEH_InitialSession、SEH_SignData 等上层接口。

包内 MsSTD.dll 的导入表列出 CryptAcquireContextA、CryptCreateHash、CryptHashData、CryptSignHashA；另可识别 Pkcs11STD.dll 和提供 SKF 导出的库。这支持“上层证书接口与设备后端分层”的观察，不证明这些后端在同一次登录中全部启用。

NSIS 包内有多个同名的 $SYSDIR/$R0 项，拆包采用自动重命名保留每个成员。当前文件到原始 DLL 名称的对应，结合 PE 版本字符串、导入及导出表识别；版本字符串属于自声明信息。MsSTD.dll 对应拆出文件 $R0_5，SafeEngine.dll 对应 $R0，不能按提取名称直接当成已安装位置。

主要证据：R06、R07、R08 和 sheca-pe-inventory.json。此样本仅用于解释历史中间件机制，不作为当前浏览器兼容或国密合规的选型结论。

## 对接入设计能提取出的结论

第一，实际样本中的 UKey 适配落在安全接入软件或证书中间件中。原业务程序可以继续使用其业务协议，由接入软件承担设备认证和通道功能；能否用于某个业务仍需具体适配证据。

第二，至少存在两种可组合的边界：界面通过本机 API 请求 Key 认证；原生通信库通过回调请求设备签名。两者可以处于同一条链路，不能简单当成互斥方案。

第三，多厂家适配可以围绕动态驱动加载及 SKF/CSP/PKCS#11 等接口组织。标准函数同名或设备库同时导出多套接口，都不能代替型号、位数、证书用途和实际调用的兼容验证。

第四，已观察到的 Key 认证与安全接入模块，并没有单独证明任意业务账号的强制关联。业务登录适配仍是另一个待研究的功能；本次也没有充分证据断言上述软件完全没有 Hook 或任何其他路径。

本轮得到的是具体样本的实现机制，不是当前项目的整体密评结论。针对所选程序的 Key 调用方式已经取得静态证据；PIN 交互、设备插拔后的已有会话处理、网关挑战及重放防护、具体业务账号关联和端到端保护范围尚未运行验证。

## REA Evidence 索引

完整 ID 和限制同时见 ../../evidence/third-party/2026-11-03/rea-evidence-index.json；表中优先列完整父记录，避免将 summary 视图当成全部结果。

| 索引 | 分析 | Evidence ID |
| --- | --- | --- |
| R01 | iSecSP libvl3vpn.so 原生导出 | ev_fa75f2f5fddb54f2aa6c0c71fb382a2061f40c865d5be25f1a5c3abbd88c0325 |
| R02 | EasyConnect 选定 6 个 JavaScript 文件 | ev_c441d5ddf50fadfb1b6d6e2a5a730ecb4a380b4964f451a5d51895fafba19b00 |
| R03 | ShuttleCsp11_3000GM.dll 导出 | ev_034e0f41816bc266ba5810dbc0ad893d13359971c5b0bd9643d95e70e40f596d |
| R04 | SangforCSClient.exe 导入 | ev_b3dd584f0d6431d93631be122b008d27be22ceecff7fcafd4ad3b8eb86f23d9e |
| R05 | ECAgent.exe 导入 | ev_b4e01f637c6f0a7e7c3d0cb5892b9476c8feebb8c04950d38e9ae2b14f5d6c82 |
| R06 | UniAgent.exe 导入 | ev_3ed3863386450a26fab6b183d690bdcf34c95853a9c3bba46bdb97505d29a02f |
| R07 | MsSTD.dll 导入 | ev_6d4ea72cf8ccba847383c4f36cef2128811b692388172f0a01852f92c25ae51d |
| R08 | SafeEngine.dll 导出 | ev_e1cc19081d022d1a9ff7bbc4b64524ff0cf8ef30761e973fc15aa833c43ef430 |
