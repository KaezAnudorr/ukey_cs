# 交接包制作入口

本目录保存交接包的制作工具和随包说明。Git 拉取后的 `handoff/` 不含 `demo/`、`source/`、`baseline/` 和包内清单，直接在这里执行 `test.cmd quick` 不具备运行条件。源码开发和本机演示请使用 [product/README.md](../product/README.md)。

## 文件用途

| 文件 | 用途 |
|---|---|
| `build-kit.py` | 汇总产品发行包、源码、网络实验脚本和历史基线，制作交接 ZIP |
| [START-HERE.md](START-HERE.md) | 接收方解压完整交接 ZIP 后的起点 |
| `test.cmd`、`test.py` | 交接包的环境检查与本机测试入口 |
| [NETWORK.md](NETWORK.md) | 在测试虚拟机复现三网区实验 |
| [REAL-PILOT.md](REAL-PILOT.md) | 公司模拟生产环境的试点记录与检查顺序 |

## 制作完整交接包

在仓库根目录先构建、打包产品：

```powershell
python product/tools/manage.py build
python product/tools/manage.py package
```

`package` 在 `product/dist/` 生成 `cs-ukey-pilot-0.2.0-demo.zip`、`cs-ukey-pilot-0.2.0-demo-source.zip` 及其校验文件。交接脚本还要求下列原始基线文件：

- `evidence/development/2026-11-06/v0.2/acceptance-result.json`
- `evidence/development/2026-11-09/network-lab/network-result.json`

这两份文件没有随 Git 提交提供，需从原交付方补齐对应历史结果。齐备后执行：

```powershell
python handoff/build-kit.py
```

输出为 `product/dist/cs-ukey-handoff-0.2.0-demo.zip`。接收方解压整个 ZIP 后，按其中的 `START-HERE.md` 操作。macOS/Linux 将上述 `python` 换为 `python3`。
