# 阶段三：Selenium 与 JMeter 测试设计

本阶段围绕 Online-Boutique 前端完成黑盒功能测试和性能测试。测试目标是验证主要用户流程是否可用，并记录页面加载时间、交互响应时间和负载测试结果。

## 测试环境

| 项目 | 内容 |
| --- | --- |
| 被测地址 | `http://127.0.0.1:8088` |
| 功能测试工具 | Python Selenium + pytest |
| 浏览器 | Microsoft Edge |
| 性能测试工具 | Apache JMeter 5.1.1 |
| Java 环境 | JDK 1.8 |

阶段三开始前，Online-Boutique 前端已通过阶段一端口转发暴露到本地 `8088` 端口。

## Selenium 功能测试设计

Selenium 测试文件：

```text
tests/selenium/online_boutique_smoke_test.py
tests/selenium/online_boutique_smoke.side
```

功能测试覆盖四个用户场景：

| 用例 | 验证内容 |
| --- | --- |
| 首页加载 | 首页可打开，并能展示商品链接 |
| 商品详情 | `OLJCESPC7Z` 商品详情页正常渲染，页面中出现 `Sunglasses` |
| 加入购物车 | 用户可以将 `Sunglasses` 以数量 `2` 加入购物车 |
| 结算流程 | 用户可以填写结算信息并看到订单完成页面 |

测试脚本同时记录两类时间指标：

- 页面加载时间：基于浏览器 Navigation Timing。
- 交互响应时间：从点击操作开始，到预期页面状态出现为止。

执行脚本：

```powershell
.\FinalProject\scripts\run-phase3-selenium.ps1
```

输出目录：

```text
data/phase3/selenium/
```

## JMeter 性能测试设计

JMeter 测试计划：

```text
tests/jmeter/online_boutique_load_test.jmx
```

测试计划模拟一个完整购物流程：

1. 打开首页。
2. 打开商品详情页。
3. 加入购物车。
4. 查看购物车。
5. 提交结算。

实际执行了三组负载：

| Run Name | 线程数 | Ramp-up | Loops | 目的 |
| --- | ---: | ---: | ---: | --- |
| `smoke-001` | 1 | 默认 | 1 | 验证 JMeter 脚本可运行 |
| `normal-001` | 10 | 20s | 5 | 模拟普通负载 |
| `higher-001` | 20 | 30s | 5 | 模拟较高负载 |

执行脚本：

```powershell
.\FinalProject\scripts\run-phase3-jmeter.ps1
```

输出目录：

```text
data/phase3/jmeter/
```

## 与阶段四的关系

阶段三主要验证系统在正常和负载访问下的功能与性能，不作为 KPIRoot 的主要故障数据来源。阶段四使用阶段二的故障注入数据作为核心输入，阶段三数据可作为系统正常可用性和高负载访问能力的补充证据。
