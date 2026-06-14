# Trading K8s Platform

> Production-grade microservices trading platform on Azure Kubernetes Service with Helm, ArgoCD, KEDA, and full observability.

[![AKS](https://img.shields.io/badge/AKS-1.30-0089D6?logo=microsoft-azure)](https://azure.microsoft.com/products/kubernetes-service)
[![Helm](https://img.shields.io/badge/Helm-3.16-0F1689?logo=helm)](https://helm.sh)
[![ArgoCD](https://img.shields.io/badge/ArgoCD-2.13-EF7B4D)](https://argoproj.github.io/cd)
[![KEDA](https://img.shields.io/badge/KEDA-2.16-FF6B35)](https://keda.sh)

---

## Services

| Service | Language | Port | Description |
|---------|----------|------|-------------|
| `market-data-service` | Python 3.12 | 8080 | Real-time price feed aggregation |
| `order-service` | Python 3.12 | 8081 | Order lifecycle management |
| `risk-service` | Python 3.12 | 8082 | Pre-trade risk checks (VaR, position limits) |
| `settlement-service` | Python 3.12 | 8083 | T+2 settlement processing |

---

## Platform Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Orchestration | AKS 1.30 | Container runtime |
| Package manager | Helm 3.16 | Kubernetes manifests |
| GitOps | ArgoCD 2.13 | Continuous deployment |
| Autoscaling | KEDA 2.16 | Event-driven scaling (RabbitMQ, Service Bus) |
| Messaging | RabbitMQ | Async inter-service communication |
| Monitoring | Prometheus + Grafana | Metrics + dashboards |
| Alerting | Alertmanager | PagerDuty integration |

---

## Quick Start

```bash
# Install prerequisites
helm repo add argo https://argoproj.github.io/argo-helm
helm repo add kedacore https://kedacore.github.io/charts

# Create namespace
kubectl create namespace trading

# Install ArgoCD
helm install argocd argo/argo-cd -n argocd --create-namespace

# Apply ArgoCD apps (GitOps from this repo)
kubectl apply -f argocd/applications/

# Check status
kubectl get pods -n trading
argocd app list
```

---

## Architecture

```
Internet
    │
    ▼
Azure Application Gateway (WAF)
    │
    ▼
AKS Cluster (3 node pools)
    ├── market-data-service  ──→  RabbitMQ (price.tick exchange)
    │                                  │
    ├── order-service  ◄──────────────┘
    │       │
    │       ├──→ risk-service (pre-trade check, gRPC, <5ms)
    │       │
    │       └──→ settlement-service (via RabbitMQ)
    │
    └── Observability
            ├── Prometheus (metrics scraping)
            ├── Grafana (dashboards)
            └── Alertmanager (PagerDuty alerts)
```

---

## GitOps with ArgoCD

All deployments managed via Git. Merging to `main` triggers ArgoCD sync:

```
git push → GitHub → ArgoCD polls → kubectl apply
```

No manual `kubectl apply` in production.

---

## KEDA Autoscaling

Order service scales based on RabbitMQ queue depth:
- 0 replicas when queue empty (scale to zero)
- 1 replica per 10 pending orders
- Max 20 replicas

---

## Observability

- **Prometheus**: scrapes `/metrics` from all services every 15s
- **Grafana**: pre-built dashboard at `monitoring/grafana/dashboards/trading-overview.json`
- **Alerts**: `monitoring/prometheus/rules/trading-alerts.yaml`
  - Order processing P99 > 100ms
  - Risk service unavailable > 30s
  - Settlement failure rate > 0.1%

---

## License

MIT
