# 桌面点击登录，先验证 UKey 再继续业务

## 用当前真实设备测试（不依赖管理平台发布）

```powershell
python -B new/run.py --mode hardware-local --java-home D:\Code\Language\Jdk_8
```

此模式调用现有云密助手和真实 UKey，读取设备证书，并用原网页登录插件 JAR 内的 Bouncy Castle 密码库独立验签。仅管理配置使用本地测试绑定：`alice` 绑定本次读取的设备和证书；随机挑战由新本地服务生成，业务仍为本机样例。

保留预填的 `alice` / `demo-password`，点击“登录并验证 UKey”，由设备持有人在本机弹窗输入自己的正确 PIN。**不要使用模拟 PIN，不在聊天中提供 PIN，不自动尝试错误 PIN。** 验签通过后还会离线检查篡改原文必须被拒绝，再继续样例业务登录。

只读检查和密码库自测（不校验 PIN、不签名）：

```powershell
python -B new/run.py --mode hardware-local --check-hardware --java-home D:\Code\Language\Jdk_8
```

当前已确认真实设备、证书和独立验签程序就绪；实际硬件签名结果需本人在窗口输入 PIN 后读取 `new/.runtime/hardware/result.json`。证书只按本次读取的精确内容固定，不代表完成 CA 信任链或吊销检查。若其他机器的 JAR 或 JDK 路径不同，可用 `--jar`、`--java-home` 指定。

2026-11-12 本人操作的实际结果：助手拒绝 PIN 验证，业务请求数为 0，尚未完成签名验签；只读查询剩余次数为 10/12。**先由持有人确认正确 PIN，不要连续试错。** 详情见 [验证记录](docs/验证记录.md)。

## 全模拟体验

在项目根目录执行：

```powershell
python -B new/run.py --mode mock
```

窗口中的业务账号和密码预填为 `alice` / `demo-password`。点击“登录并验证 UKey”后，原业务登录暂停，弹出安全认证窗口；输入**仅用于模拟的 PIN `123456`**，认证通过后才提交业务登录。取消、错误 PIN 或验签失败都会停止本次登录。

全模拟模式不访问现有管理平台、不调用真实 UKey，也不会尝试真实设备的 PIN。桌面端使用 Python 3.10+ 标准库与 Tkinter；全模拟模式不依赖 Java，真实硬件本地验签模式复用已有 JDK 8+ 和原 JAR 的密码库，无需额外 pip 包。旧 Java DEMO 的 Java 17+ 要求没有改变。

## 一键测试

```powershell
python -B new/run.py --mode mock --smoke
python -B new/tests/run_tests.py
```

测试从真实 HTTP 请求和 TCP 样例业务验证：取消、错误 PIN、无设备、设备改变、账号/应用不匹配、签名篡改、挑战及授权过期/重放，以及真实接口适配的 504、未发布配置和失败验签。自动测试使用模拟设备与本地接口替身，不输入真实 PIN。

运行结果写入 `new/.runtime/login-tests.json`；可公开的测试摘要在 `tests/results/desktop-login-tests.json`，桌面检查记录在 [验证记录](docs/验证记录.md)。

## 真实接入入口已保留

先只读检查当前真实助手：

```powershell
python -B new/run.py --mode nmr --probe-helper
```

管理平台发布恢复后，确认目标 NMR 实例发布的就是指定应用，再执行：

```powershell
python -B new/run.py --mode nmr --nmr-url http://127.0.0.1:9191 --helper-url http://127.0.0.1:38080 --app-id 911663C3414F4061B2F97E425D415FC0
```

此模式调用现有助手和 NMR 接口，PIN 只发送到本机助手；它仍连接本次新建的本机样例业务，不接入现网业务。NMR 缺配置、504、验签失败或设备不可用时阻止登录，**不会退回模拟模式**。自动 smoke 禁止在真实模式运行。

管理平台发布仍未完成，因此**NMR 密码服务验签和实际平台配置联调尚未通过**。`hardware-local` 可独立验证真实设备签名，不会宣称 NMR 已发布或现网密码服务已验签成功；其实际签名结果以本人 PIN 操作后的记录为准。不能把全模拟模式与真实助手混用并将任意签名视作通过。

详见 [真实适配与测试边界](docs/真实适配.md)。

## 文件按职责分类

| 位置 | 内容 |
|---|---|
| `run.py` | 显式选择模拟/真实模式，启动 GUI、smoke 或只读设备探测 |
| `src/desktop.py` | 新增原生桌面样例与 PIN 窗口 |
| `src/workflow.py` | 暂停登录、调用助手、证明认证、继续业务登录 |
| `src/adapters.py` | 云密助手与 NMR 真实 HTTP 适配、模拟管理配置与模拟验签 |
| `src/hardware.py`、`src/java/HardwareVerifier.java` | 真实设备本地绑定、复用原 JAR 密码库的独立 SM2 验签 |
| `src/service.py` | 本次登录挑战、一次性授权和独立 TCP 样例业务 |
| `src/mock_helper.py` | 仅模拟模式使用的助手协议替身 |
| `src/runtime.py` | 本次创建服务的启动/停止，不占用旧插件端口 |
| `tests/` | 自动测试、已有设备探测和脱敏实验结果 |
| `docs/` | 中文变更、运行与适配说明 |
| `.runtime/` | 不上传的运行结果、构建产物和日志 |

## 仍需完成的业务适配

这个新增桌面样例验证点击登录的完整交互，不是对任意已有 EXE 的通用拦截器，也没有改造旧 Java 客户端。真实业务需另行接入其登录触发和业务请求入口。

样例业务原端口仍可直接访问，本机 HTTP 接口也不鉴别 OS 用户/进程。因此当前是回环环境功能实验，没有完成生产防绕行、端到端国密通道或商密验收。

`../ukey/`、`../web-plugin/` 原项目代码不改动；原根 README 保留历史状态，当前入口以本页为准。后续改动在本目录完成，使用中文提交并推送到 <https://github.com/KaezAnudorr/ukey_cs>。

查看 [中文变更记录](docs/CHANGELOG.md) 与 [上传范围](docs/上传范围.md)。
