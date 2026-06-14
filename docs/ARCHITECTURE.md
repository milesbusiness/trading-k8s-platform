# Trading K8s Platform — Architecture

## Overview

A production-grade trading platform running as four microservices on Azure Kubernetes Service, with Helm packaging, ArgoCD GitOps deployment, KEDA event-driven autoscaling, and full Prometheus + Grafana observability.

---

## Service Architecture

```
Internet
    │
    ▼
Azure Application Gateway (WAF + TLS termination)
    │
    ▼
AKS Ingress Controller (NGINX)
    │
    ├─────────────────────────────────────────────────────┐
    │                                                     │
    ▼                                                     ▼
market-data-service :8080              order-service :8081
  - Aggregates price feeds               - REST API for order submission
  - Publishes tick events to RabbitMQ    - Calls risk-service (gRPC, <5ms)
  - 2 replicas (static)                  - KEDA: scales 0→20 on queue depth
    │                                     │
    │ (price.tick exchange)               │ (pre-trade check)
    ▼                                     ▼
RabbitMQ Cluster                       risk-service :8082
  - 3 nodes (HA)                         - In-memory position limits
  - Durable exchanges                    - VaR check (simplified)
  - Persistent volumes (20Gi)            - 3 replicas, PDB minAvailable=2
    │                                     │
    │ (order.executed events)             │ (settlement instruction)
    ▼                                     ▼
settlement-service :8083
  - T+2 settlement processing
  - CSDR compliance tracking
  - 2 replicas
```

---

## KEDA Autoscaling (Order Service)

```yaml
# Order service scales based on RabbitMQ queue depth
ScaledObject:
  scaleTargetRef: order-service
  minReplicaCount: 0          # Scale to zero when no orders
  maxReplicaCount: 20
  triggers:
    - type: rabbitmq
      queueName: orders
      mode: QueueLength
      value: "10"             # 1 replica per 10 queued orders
```

This means:
- **Quiet period:** 0 replicas (zero cost)
- **10 pending orders:** 1 replica
- **100 pending orders:** 10 replicas
- **200 pending orders:** 20 replicas (max)

---

## GitOps with ArgoCD

```
Developer pushes to main
        │
        ▼
GitHub Actions CI
  ├── Build 4 service images
  ├── Trivy container scan
  ├── Push to GHCR
  └── Trigger ArgoCD sync
        │
        ▼
ArgoCD polls git repo
  └── Detects image tag change in values.yaml
        │
        ▼
kubectl apply (automated)
  └── Rolling update (maxUnavailable=0, maxSurge=1)
```

**No manual kubectl in production.** Every change goes through Git.

---

## Observability Stack

```
Services expose /metrics (Prometheus format)
        │
        ▼
Prometheus (scrapes every 15s)
        │
        ├─────────────────────┐
        ▼                     ▼
Grafana Dashboard        Alertmanager
  - Order throughput       - OrderServiceHighLatency (P99 > 100ms)
  - Risk check rates       - RiskServiceDown (> 30s)
  - Settlement status      - HighSettlementFailureRate (> 0.1%)
  - Queue depth            → PagerDuty
```

Key metrics per service:
- `orders_submitted_total{status="accepted|rejected"}` — order funnel
- `order_processing_seconds` — P99 latency histogram
- `risk_checks_total{result="approved|rejected"}` — risk check rates
- `settlements_created_total` — settlement throughput
- `market_data_ticks_published_total{symbol}` — feed health

---

## Helm Chart Structure

```
helm/charts/trading-platform/
├── Chart.yaml           ← chart metadata
├── values.yaml          ← default values (all services)
└── templates/
    ├── market-data-deployment.yaml
    ├── order-service-deployment.yaml
    ├── order-service-keda.yaml      ← ScaledObject + TriggerAuth
    ├── risk-service-deployment.yaml
    ├── settlement-service-deployment.yaml
    └── rabbitmq.yaml
```

---

## Why Four Services (Not One)?

| Service | Scaling profile | Failure impact |
|---------|----------------|----------------|
| market-data | CPU-bound, constant | Feed disruption only |
| order | Burst (KEDA) | Revenue impact |
| risk | Always-on, PDB enforced | All orders blocked |
| settlement | Batch, T+2 | Regulatory impact (CSDR) |

Each service scales independently. Risk service has strict PDB (`minAvailable: 2`) — losing it blocks all order flow, so it is never fully cycled in a rolling update.

---

## References

### Kubernetes & AKS
- [AKS docs — Production best practices](https://learn.microsoft.com/en-us/azure/aks/best-practices)
- [Kubernetes docs — Pod Disruption Budgets](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/)
- [YouTube: Kubernetes production best practices (TechWorld with Nana, 45 min)](https://www.youtube.com/watch?v=fy8SHvNZGeE)

### KEDA
- [KEDA docs — RabbitMQ scaler](https://keda.sh/docs/scalers/rabbitmq-queue/)
- [KEDA docs — Scale to zero](https://keda.sh/docs/concepts/scaling-deployments/#scaling-to-zero)
- [YouTube: KEDA — Kubernetes Event-Driven Autoscaling (Microsoft, 30 min)](https://www.youtube.com/watch?v=3lcaawKAv6s)

### ArgoCD / GitOps
- [ArgoCD docs](https://argo-cd.readthedocs.io/en/stable/)
- [GitOps principles (OpenGitOps)](https://opengitops.dev/)
- [YouTube: ArgoCD Tutorial for Beginners (TechWorld with Nana, 1h45m)](https://www.youtube.com/watch?v=MeU5_k9ssrs)

### Helm
- [Helm docs — chart development](https://helm.sh/docs/chart_template_guide/)
- [YouTube: Helm crash course (freeCodeCamp, 1h)](https://www.youtube.com/watch?v=gg-GuHs8Nsk)

### Prometheus & Alerting
- [Prometheus docs — alerting rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
- [PromQL cheat sheet](https://promlabs.com/promql-cheat-sheet/)
- [YouTube: Prometheus monitoring tutorial (TechWorld with Nana, 2h)](https://www.youtube.com/watch?v=h4Sl21AKiDg)

### Trading Microservices
- [MiFID II — Algorithmic trading requirements (Art. 17)](https://www.esma.europa.eu/publications-and-data/interactive-single-rulebook/mifid-ii/article-17)
- [CSDR settlement fails reporting (Art. 7)](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014R0909)
