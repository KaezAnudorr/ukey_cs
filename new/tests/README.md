# 新增测试

## 桌面登录流程与真实接口契约

```powershell
python -B new/tests/run_tests.py
python -B new/run.py --mode mock --smoke
```

`test_login.py` 在回环地址运行助手、NMR 接口替身和样例业务，通过 HTTP/TCP 验证正常登录和拒绝路径；不访问真实管理平台、不尝试真实 PIN。测试原理与边界见 [真实适配](../docs/真实适配.md)，汇总写到 `new/.runtime/login-tests.json`。

图形实验：`python -B new/run.py --mode mock`。仅模拟 PIN 为 `123456`，业务账号密码为 `alice` / `demo-password`。不要向真实设备尝试此模拟 PIN。

## Java 8 设备识别探测

在工作目录根路径打开 PowerShell，保持云密 UKey 助手运行且插入设备：

```powershell
$out = '.\new\.runtime\java8-device-probe'
New-Item -ItemType Directory -Force $out | Out-Null
& 'D:\Code\Language\Jdk_8\bin\javac.exe' -d $out .\new\tests\environment\Java8DeviceProbe.java
if ($LASTEXITCODE -eq 0) {
    & 'D:\Code\Language\Jdk_8\bin\java.exe' -cp $out Java8DeviceProbe
}
```

其他机器将 JDK 路径替换为本机路径。探测调用 `http://127.0.0.1:38080/sys/getDevInfo`，预期输出 `http.status=200` 和 `device.detected=true`，退出码 0；未识别设备时退出码 2，连接失败会直接报错。

这只验证 Java 8 能调用助手并读取设备信息，不验证 PIN、证书信任、设备签名或业务登录。代码不输出设备序列号。

## 已有实验结果

`results/` 保存此前本机实验的脱敏结果：Java 环境、37 项测试摘要、内置客户端正反向登录实验。它们不是刚从 GitHub 拉取后自动重新执行的结果。原有 37 项测试源码仍在 `ukey/product/access-server/src/test/`，未改动。
