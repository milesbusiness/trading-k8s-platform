# Trading K8s Platform

> **Production-grade trading infrastructure on Azure Kubernetes Service — four microservices, event-driven autoscaling, GitOps deployment, and full MiFID II observability.**

[![AKS](https://img.shields.io/badge/AKS-1.30-0089D6?logo=microsoft-azure)](https://azure.microsoft.com/products/kubernetes-service)
[![KEDA](https://img.shields.io/badge/KEDA-2.15-326CE5)](https://keda.sh)
[![ArgoCD](https://img.shields.io/badge/ArgoCD-2.12-EF7B4D)](https://argoproj.github.io/cd)
[![Helm](https://img.shields.io/badge/Helm-3.16-0F1689)](https://helm.sh)
[![Prometheus](https://img.shields.io/badge/Prometheus-2.55-E6522C?logo=prometheus)](https://prometheus.io)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## The Problem

A trading firm's technology platform must satisfy requirements that are fundamentally in tension with each other:

**High availability** — The risk service must never go down. An outage means every order is rejected. That is lost revenue and potential regulatory breach.

**Cost efficiency** — Order flow is not constant. Peak trading occurs in the first hour of the market session. During quiet periods, paying for 20 idle order-processing servers is pure waste.

**Zero downtime deployment** — A trading platform cannot be taken offline for upgrades during market hours. Changes must be deployed while the system continues to serve live traffic.

**Regulatory compliance** — MiFID II requires algorithmic trading systems to be monitored in real-time with automated circuit breakers. CSDR requires settlement failure rates to be tracked and reported.

**Security** — Financial platforms are high-value attack targets. Every container must run with minimum privileges. No secrets in code or configuration files.

Meeting all of these simultaneously with a monolithic application is impossible. This platform demonstrates how to achieve all of them using Kubernetes microservices.

## The Solution

Four independent microservices, each with its own scaling profile, database, and deployment lifecycle — running on Azure Kubernetes Service with GitOps deployment, event-driven autoscaling, and comprehensive observability.

---

## The Four Services

### Market Data Service
**What it does:** Aggregates real-time price feeds (FX rates, equity prices, volatility surfaces) and publishes tick events to RabbitMQ for consumption by the other services.

**Scaling:** 2 replicas, static (constant workload — price feeds are always on).

**Key metric:** `market_data_ticks_published_total{symbol}` — alerts if feed goes stale.

### Order Service
**What it does:** Receives trade orders via REST API. Before accepting any order, calls the risk service synchronously to check position limits. Accepted orders are published to the execution queue.

**Scaling:** KEDA scales this service **from 0 to 20 replicas** based on RabbitMQ queue depth:
- 0 orders waiting = 0 replicas (zero cost during quiet periods)
- 50 orders waiting = 5 replicas
- 200 orders waiting = 20 replicas

**Key metric:** `order_processing_seconds` P99 — alerts if > 100ms (MiFID II Art. 17 algorithmic trading monitoring).

### Risk Service
**What it does:** Checks every single order in under 5 milliseconds against:
- Position limits (maximum exposure per trader)
- Daily notional limits (maximum trading volume per day)
- Concentration limits (maximum exposure to a single instrument as % of portfolio)

**Scaling:** Fixed at minimum 2 replicas. PodDisruptionBudget ensures at least 2 are always running — even during Kubernetes node upgrades, the risk service is never fully cycled. This is non-negotiable: if the risk service goes down, all order flow stops.

**Key metric:** `risk_check_duration_ms` P99 — must remain below 5ms. `risk_service_down` alert pages on-call immediately.

### Settlement Service
**What it does:** Processes post-trade settlement instructions (T+2 basis), tracks failed settlements, and reports CSDR compliance. Every executed trade becomes a settlement instruction within 30 seconds.

**Scaling:** 2 replicas, scales based on settlement queue depth.

**Key metric:** `settlement_failure_rate` — alerts if > 0.1% (CSDR Art. 7 reporting threshold).

---

## Infrastructure Design

```
Internet
    │
    ▼
Azure Application Gateway (WAF + TLS 1.3)
    │
    ▼
AKS Ingress (NGINX)
    ├─────────────────────────────────────────────┐
    │                                             │
    ▼                                             ▼
market-data-service (2 replicas)      order-service (0–20 replicas, KEDA)
    │                                             │
    │ Publishes to RabbitMQ                       │ Calls risk-service (gRPC, <5ms)
    ▼                                             ▼
RabbitMQ Cluster (3 nodes, HA)        risk-service (min 2 replicas, PDB enforced)
    │                                             │
    ▼                                             ▼
settlement-service (2 replicas)     ◄─── order.executed events
    │
    ▼
Azure SQL (settlement records, T+2 processing)

Observability Layer (all services)
    └── Prometheus metrics → Alertmanager → PagerDuty
    └── Grafana dashboards
```

---

## GitOps Deployment (ArgoCD)

No manual `kubectl apply` commands in production. Every deployment happens through Git:

```
Developer pushes code → GitHub
    │
    ▼
GitHub Actions CI
  ├── Build Docker images
  ├── Trivy container security scan
  └── Push to GHCR with semantic version tag
    │
    ▼
Update Helm values.yaml with new image tag → Git commit
    │
    ▼
ArgoCD detects change (polls every 3 minutes)
    │
    ▼
kubectl apply (rolling update, maxUnavailable=0)
    │
    ▼
New pods start → health checks pass → old pods terminate
Zero downtime throughout
```

If the deployment breaks anything, ArgoCD detects drift and can automatically roll back to the last known good state.

---

## Observability and Alerting

### Prometheus Metrics (per service)

| Metric | Type | Alert Threshold |
|--------|------|----------------|
| `orders_submitted_total{status}` | Counter | — |
| `order_processing_seconds` | Histogram | P99 > 100ms → page |
| `risk_checks_total{result}` | Counter | — |
| `risk_check_duration_ms` | Histogram | P99 > 5ms → warn |
| `risk_service_up` | Gauge | 0 for > 30s → critical page |
| `settlements_created_total` | Counter | — |
| `settlement_failure_rate` | Gauge | > 0.001 (0.1%) → CSDR alert |
| `market_data_ticks_published_total` | Counter | Stale for 60s → warn |

### Regulatory Alerts

| Alert | Regulation | Action |
|-------|-----------|--------|
| `RiskServiceDown` | MiFID II Art. 17 | Page on-call immediately, halt new orders |
| `HighSettlementFailureRate` | CSDR Art. 7 | Page compliance team, log for reporting |
| `OrderServiceHighLatency` | MiFID II Art. 17 | Alert engineering, review algo controls |

---

## KEDA Autoscaling Details

```yaml
ScaledObject for order-service:
  minReplicaCount: 0          # Scales to zero when no orders
  maxReplicaCount: 20         # Maximum 20 processing workers
  triggers:
    type: rabbitmq
    queueName: orders
    value: "10"               # Target 10 messages per replica

Scaling examples:
  Queue depth 0    → 0 replicas  (cost: €0)
  Queue depth 10   → 1 replica
  Queue depth 50   → 5 replicas
  Queue depth 100  → 10 replicas
  Queue depth 200  → 20 replicas (capped)
```

Cost saving on a typical trading desk: **60–70% reduction** in order service compute costs compared to always-on provisioning.

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Container orchestration | Azure AKS 1.30 | Production Kubernetes managed service |
| Autoscaling | KEDA 2.15 | Event-driven scale-to-zero on RabbitMQ |
| GitOps | ArgoCD 2.12 | Automated deployment from Git |
| Package management | Helm 3.16 | Kubernetes configuration templating |
| Message broker | RabbitMQ 3.13 (3-node HA) | Async inter-service communication |
| Metrics | Prometheus 2.55 | Service metrics collection |
| Dashboards | Grafana 11 | Real-time trading operations visibility |
| Services | Python 3.12 + FastAPI | Lightweight, async microservices |
| Networking | NGINX Ingress + Calico CNI | Ingress + network policy enforcement |

---

## Getting Started

### Local Development (Docker Compose)
```bash
git clone https://github.com/milesbusiness/trading-k8s-platform
cd trading-k8s-platform
docker-compose up

# Services:
# http://localhost:8080  order-service
# http://localhost:8081  risk-service
# http://localhost:8082  market-data-service
# http://localhost:8083  settlement-service
# http://localhost:15672 RabbitMQ management UI
```

### Test the Full Order Flow
```bash
# Submit an order (triggers risk check automatically)
curl -X POST http://localhost:8080/api/orders \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EURUSD","side":"BUY","quantity":100000,"trader_id":"t1"}'

# Check risk positions
curl http://localhost:8081/api/risk/positions

# View Prometheus metrics
curl http://localhost:8080/metrics | grep orders_submitted
```

### Deploy to AKS
```bash
# Install KEDA and ArgoCD (one-time)
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda -n keda --create-namespace

helm repo add argo https://argoproj.github.io/argo-helm
helm install argocd argo/argo-cd -n argocd --create-namespace

# Apply ArgoCD application — GitOps takes over from here
kubectl apply -f argocd/applications/trading-platform-app.yaml
```

---

## Business Value

| Requirement | Solution | Benefit |
|-------------|---------|---------|
| Zero downtime deployments | Rolling update + PDB | Deploy during market hours |
| Cost during quiet periods | KEDA scale-to-zero | 60–70% compute cost reduction |
| MiFID II Art. 17 monitoring | Prometheus + Alertmanager | Real-time circuit breaker alerting |
| CSDR settlement tracking | settlement-service metrics | Automated compliance reporting |
| Deployment consistency | ArgoCD GitOps | No manual kubectl in production |
| High availability | Multi-replica + PDB + AKS multi-AZ | 99.9%+ uptime per service |

---

## Documentation

| Document | Description |
|----------|-------------|
| [Executive Summary](docs/EXECUTIVE_SUMMARY.md) | Business case, cost analysis, compliance coverage |
| [Architecture Guide](docs/ARCHITECTURE.md) | Service design, KEDA scaling, GitOps flow, alerting |
| [Development Guide](docs/DEVELOPMENT.md) | Local setup, AKS deployment, Helm configuration |

---

## About

Built to demonstrate production Kubernetes architecture for regulated trading platforms, targeting Principal Architect, Platform Engineering Lead, and Cloud Architect roles at European financial institutions.

**Author:** Dilip Kumar Jena | **Platform:** Azure AKS | **Regulation:** MiFID II Art. 17, CSDR Art. 7
