# 阶段三：执行记录

执行日期：2026-06-05

本阶段完成 Selenium 功能测试和 JMeter 性能测试。测试对象为阶段一部署的 Online-Boutique 前端：

```text
http://127.0.0.1:8088
```

## 准备文件

阶段三使用的测试文件和运行脚本如下：

- `tests/selenium/online_boutique_smoke_test.py`
- `tests/selenium/online_boutique_smoke.side`
- `tests/jmeter/online_boutique_load_test.jmx`
- `scripts/run-phase3-selenium.ps1`
- `scripts/run-phase3-jmeter.ps1`

## 工具环境

| 工具 | 检查结果 |
| --- | --- |
| Online-Boutique frontend | `http://127.0.0.1:8088` 可访问 |
| Apache JMeter | 5.1.1，路径为 `D:\Study\jmeter\apache-jmeter-5.1.1` |
| Java | 1.8 可用 |
| 浏览器 | Microsoft Edge 可用 |
| Python Selenium | 已安装到项目级 Python 环境 |

测试环境中未检测到 Google Chrome，因此实际浏览器兼容性证据来自 Microsoft Edge。Selenium 运行脚本仍保留 Chrome 参数支持。

## Selenium 功能测试结果

执行命令：

```powershell
.\FinalProject\scripts\run-phase3-selenium.ps1
```

执行结果：

- 收集测试用例：4 个。
- 通过测试用例：4 个。
- 使用浏览器：Microsoft Edge。
- 测试截图保存在 `data/phase3/selenium/screenshots/`。
- 时间指标保存在 `data/phase3/selenium/timing_metrics.csv`。

截图文件：

- `data/phase3/selenium/screenshots/01_selenium_home_page.png`
- `data/phase3/selenium/screenshots/02_selenium_product_detail.png`
- `data/phase3/selenium/screenshots/03_selenium_cart_with_product.png`
- `data/phase3/selenium/screenshots/04_selenium_order_complete.png`

时间指标：

| 测试用例 | 指标 | 类型 | 时间 ms |
| --- | --- | --- | ---: |
| `test_home_page_lists_products` | `home_page_load_ms` | 页面加载 | 1803.10 |
| `test_product_detail_page` | `product_detail_page_load_ms` | 页面加载 | 1750.60 |
| `test_add_to_cart` | `add_to_cart_interaction_ms` | 交互响应 | 165.09 |
| `test_checkout_flow` | `checkout_submit_interaction_ms` | 交互响应 | 228.88 |

页面加载指标来自浏览器 Navigation Timing；交互响应指标记录从点击动作开始到页面出现预期状态之间的耗时。

## JMeter 性能测试结果

执行了三组 JMeter 测试。

Smoke 测试：

```powershell
.\FinalProject\scripts\run-phase3-jmeter.ps1 -Threads 1 -Loops 1 -RunName smoke-001
```

普通负载：

```powershell
.\FinalProject\scripts\run-phase3-jmeter.ps1 -Threads 10 -RampUp 20 -Loops 5 -RunName normal-001
```

较高负载：

```powershell
.\FinalProject\scripts\run-phase3-jmeter.ps1 -Threads 20 -RampUp 30 -Loops 5 -RunName higher-001
```

结果汇总：

| Run | Main Samples | Raw Samples | Errors | Error % | Avg ms | Median ms | P90 ms | P95 ms | P99 ms | Max ms | Throughput/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `smoke-001` | 5 | 7 | 0 | 0.0 | 31.80 | 36.00 | 49.80 | 51.40 | 52.68 | 53 | 36.50 |
| `normal-001` | 250 | 350 | 0 | 0.0 | 35.83 | 22.00 | 77.00 | 83.00 | 94.53 | 105 | 13.39 |
| `higher-001` | 500 | 700 | 0 | 0.0 | 33.53 | 23.00 | 73.00 | 78.00 | 91.00 | 145 | 17.10 |

`Raw Samples` 包含加入购物车流程产生的重定向子请求；`Main Samples` 只统计五个设计中的主采样器。

JMeter 产物：

- `data/phase3/jmeter/summary.csv`
- `data/phase3/jmeter/smoke-001/result.jtl`
- `data/phase3/jmeter/normal-001/result.jtl`
- `data/phase3/jmeter/higher-001/result.jtl`
- `data/phase3/jmeter/higher-001/screenshots/01_jmeter_higher_dashboard_apdex_requests.png`
- `data/phase3/jmeter/higher-001/screenshots/02_jmeter_higher_statistics_errors.png`

JMeter HTML Dashboard 也已在本地生成，但其静态资源体积较大，仓库通过 `.gitignore` 排除了 `html-report/` 目录。

## 测试后集群状态

测试结束后检查 Online-Boutique 和 ChaosMesh 状态：

- Online-Boutique Pod 均保持 `Running`。
- `online-boutique` 命名空间中无残留 ChaosMesh 对象。
- Selenium 与 JMeter 测试均未破坏后续阶段所需的微服务运行环境。

阶段三完成后，项目已获得功能测试通过结果、页面加载/交互响应时间和三组负载测试统计数据。
