# UKey 工作目录

当前任务先验证旧版网页登录安全性插件，完成真实 UKey 登录基线后再开展 C/S 业务适配。网页登录验证入口为 [web-plugin/](web-plugin/README.md)，已有 C/S 演示工程和设计资料位于 [ukey/](ukey/README.md)。两者属于产品演进的不同阶段，使用各自的启动入口。

## 文件位置

| 位置 | 用途 |
|---|---|
| [web-plugin/](web-plugin/README.md) | 按 V1.1.5 手册部署的网页登录插件，含 JAR、配置、Windows/Linux 脚本和日志 |
| [web-plugin/docs/](web-plugin/docs/登录安全性插件部署V1.1.5.pdf) | 用户提供的原始部署手册 |
| `web-plugin/reference/main-interceptor-all.js` | 手册 6.2 手动引入方式的参考脚本，当前代理方式使用 JAR 内的 JS |
| [ukey/product/](ukey/product/README.md) | C/S 接入服务、桌面 Agent、公共库和样例业务源码 |
| [ukey/docs/](ukey/docs/README.md) | 需求、设计、调研、交付计划及已有架构说明 |
| [ukey/handoff/](ukey/handoff/README.md) | 交接包制作脚本和接收方操作说明 |
| [ukey/lab/network/](ukey/lab/network/README.md) | Debian 三网区网络实验 |

原目录中的 `登录安全性插件拦截架构.md` 已移至 [ukey/docs/research/登录安全性插件拦截架构.md](ukey/docs/research/登录安全性插件拦截架构.md)。

## 网页插件启动与测试

本次共用现有管理平台、密码服务和 `192.168.1.15` 上的测试业务系统。用户已新建平台应用 `test`，应用 ID 为 `911663C3414F4061B2F97E425D415FC0`。截图已确认 nmr 地址为本机 `192.168.100.66:9191`、代理端口为 8082；字段清单见下方部署说明。2026-11-11 实测插件和 UKey 助手正常、设备已识别，但本机无平台配置和账号规则，8082 连接被拒绝；用户截图确认发布接口返回 504，发布未完成。管理平台首页和未认证接口响应可达，业务登录页访问超时。下一步由平台管理员从 NMR 后端服务器或容器探测到本机 9191 的连接，并核查发布接口的服务端日志，再完成发布及登录测试。

```powershell
cd .\web-plugin
powershell -NoProfile -ExecutionPolicy Bypass -File .\check.ps1
# 仅在插件未运行时启动：
.\start.cmd
```

文件说明、管理平台字段和完整测试步骤见 [web-plugin/README.md](web-plugin/README.md)。原启动配置及 Linux 脚本保存在 `web-plugin/backups/`，原日志保留在 `web-plugin/logs/`。

## C/S 源码与开发入口

2026-11-10 从 `http://192.168.2.147:8090/chenhx/ukey.git` 拉取，分支 `main`，拉取时提交为 `44bfca7`。Git 仓库位于 `ukey/`，当前目录本身不是 Git 仓库。

源码要求 JDK 17+、Python 3.10+ 和 Maven 3.9+。本机默认 `java` 是 JDK 8；构建 C/S 项目前，在当前 PowerShell 会话选择已有工具链：

```powershell
cd .\ukey
$env:JAVA_HOME = 'D:\Code\Language\Jdk'
$env:PATH = "$env:JAVA_HOME\bin;D:\Code\Language\Maven\apache-maven-3.9.16\bin;$env:PATH"
python product/tools/manage.py build
python product/tools/manage.py demo-init
python product/tools/manage.py smoke
```

以上命令从工作目录根路径执行，环境变量仅作用于当前 PowerShell 会话。运行和配置说明见 [产品 README](ukey/product/README.md)。历史报告、旧插件完整源码和 C/S 二进制交付包没有随本次 Git 拉取提供，详见[资料缺口](ukey/docs/README.md#未随仓库提供的材料)。
