# Anomaly Detector Microservice

这是为第三档目标补充开发的自研微服务。它将 USAD 异常检测能力封装为 HTTP API，可作为 Online Boutique、TrainTicket、SockShop 等微服务系统的智能运维组件接入。

## API

- `GET /health`：健康检查。
- `GET /summary`：返回最近一次检测摘要。
- `POST /detect`：提交 CSV 路径并运行 USAD 检测。

请求示例：

```json
{
  "input": "/app/data/prometheus_sockshop_metrics.csv",
  "out": "/app/outputs",
  "window": 12,
  "epochs": 180
}
```

响应示例：

```json
{
  "status": "ok",
  "summary": {
    "precision": "0.5889",
    "recall": "1.0000",
    "f1": "0.7413"
  }
}
```

## 本地运行

在 `final_project` 目录下：

```powershell
python services/anomaly-detector/app.py --host 127.0.0.1 --port 8088
```

另开终端：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8088/detect `
  -Body '{"input":"data/sample_sockshop_metrics.csv","out":"outputs_service"}' `
  -ContentType 'application/json'
```

## 容器化

```powershell
docker build -f services/anomaly-detector/Dockerfile -t anomaly-detector:latest .
docker run --rm -p 8088:8088 anomaly-detector:latest
```

