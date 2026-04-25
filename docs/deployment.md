# Deployment

当前只提供本地基础设施：

```bash
docker compose up -d postgres redis
```

本阶段不启动 Hummingbot，不配置真实交易所密钥。后续接入顺序：

1. 本地 Hummingbot paper mode。
2. Hummingbot API。
3. 本系统 trader gateway 调用 Hummingbot API。
4. Grafana/Prometheus 指标。
5. 告警渠道。
