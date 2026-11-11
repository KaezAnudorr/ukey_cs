# 复现三网区实验

终端、网关和样例业务服务分别运行在 Debian 内的三个网络命名空间。实验建立两段虚拟链路，检查未授权访问、原端口直连、授权业务传输、弱网和连接恢复。已有防火墙计数和链路统计的样例结果在 `baseline/network-result.json`。

## Windows、Linux 或其他主机上的 Debian 虚拟机

将交接包复制到一台一次性 Debian 12 虚拟机并解压。管理员先准备运行依赖，再从解压根目录执行实验。以下命令假设虚拟机可访问其软件仓库。

```sh
sudo apt-get update
sudo apt-get install -y python3 openjdk-17-jre-headless iproute2 iptables socat
sudo python3 -B lab/network/guest.py demo ./network-result-01
```

最后一个参数是尚不存在的输出目录。脚本在虚拟机内创建和清理测试命名空间、路由和防火墙规则。主要交接结果是该目录下的 `network-result.json`。现场已经有安装好依赖的虚拟机时，可以直接执行第三条命令。

## Apple Silicon Mac

安装 Apple 命令行工具。在交接包的解压根目录运行以下命令。

```sh
python3 lab/network/run-mac.py --bundle demo --output ./network-vm-01
```

首次运行下载约 266 MB 的 Debian 镜像并校验。实验需联网准备虚拟机软件包，虚拟机分配 2 核和 3 GiB 内存。运行结束后查看 `network-vm-01/share/results/network-result.json`。

本实验使用样例业务和软件证书。它能验证虚拟网络中的受控路径，仍需在真实环境复测原业务端口、备用路径、现场防火墙、同机用户隔离和硬件身份。
