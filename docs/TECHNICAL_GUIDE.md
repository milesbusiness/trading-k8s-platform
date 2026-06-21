# Technical Guide — Trading K8s Platform

> This guide explains every technology used, how to learn it, how to install the project, what every file does, and how to see the output.

---

## Table of Contents

1. [Technologies Used](#1-technologies-used)
2. [Where to Learn Each Technology](#2-where-to-learn-each-technology)
3. [Installation — Step by Step](#3-installation--step-by-step)
4. [Project File Structure](#4-project-file-structure)
5. [Code Walkthrough — Every File Explained](#5-code-walkthrough--every-file-explained)
6. [How to Run and View Output](#6-how-to-run-and-view-output)

---

## 1. Technologies Used

| Technology | Version | What it is | Why it is used here |
|-----------|---------|-----------|-------------------|
| **Kubernetes (AKS)** | 1.30 | Container orchestration platform | Runs and manages all 4 microservices; handles scaling, restarts, rolling updates |
| **Azure Kubernetes Service** | — | Microsoft's managed Kubernetes | Removes the burden of managing Kubernetes control plane; integrates with Azure monitoring |
| **Python 3.12 + FastAPI** | — | Language + web framework | All 4 microservices are Python FastAPI applications |
| **KEDA** | 2.15 | Kubernetes Event-Driven Autoscaling | Scales the order-service from 0→20 replicas based on RabbitMQ queue depth |
| **RabbitMQ** | 3.13 | Message broker | Async communication between services; queues orders for processing |
| **ArgoCD** | 2.12 | GitOps continuous delivery tool | Watches GitHub, auto-deploys when Helm values change; enforces Git as source of truth |
| **Helm** | 3.16 | Kubernetes package manager | Templates and packages all Kubernetes manifests; handles environment differences |
| **Prometheus** | 2.55 | Metrics collection and alerting | Scrapes metrics from all 4 services; fires alerts when thresholds are breached |
| **Grafana** | 11 | Metrics dashboards | Visualises Prometheus metrics in real-time dashboards |
| **prometheus-client** | Python | Python library for Prometheus metrics | Used inside each service to expose `Counter` and `Histogram` metrics |
| **httpx** | Python | Async HTTP client | Order service calls risk service synchronously via HTTP |
| **Docker** | — | Container runtime | Each service is packaged as a Docker image |
| **NGINX Ingress** | — | Kubernetes ingress controller | Routes external HTTP traffic to the correct service |
| **Calico** | — | Kubernetes network policy | Enforces network isolation between pods |

**Official Links:**
- Kubernetes: https://kubernetes.io/docs/home/
- AKS: https://learn.microsoft.com/azure/aks/
- KEDA: https://keda.sh/docs/
- ArgoCD: https://argo-cd.readthedocs.io/
- Helm: https://helm.sh/docs/
- Prometheus: https://prometheus.io/docs/introduction/overview/
- RabbitMQ: https://www.rabbitmq.com/documentation.html
- prometheus-client Python: https://github.com/prometheus/client_python

---

## 2. Where to Learn Each Technology

### Kubernetes

**Official:**
- https://kubernetes.io/docs/tutorials/kubernetes-basics/ — Interactive tutorial (free, runs in browser)
- https://kubernetes.io/docs/concepts/ — Core concepts (Pods, Deployments, Services, etc.)

**YouTube:**
- "Kubernetes Tutorial for Beginners" by TechWorld with Nana — https://www.youtube.com/@TechWorldwithNana (most popular K8s channel)
- "Kubernetes crash course" by freeCodeCamp — https://www.youtube.com/@freecodecamp

**What to focus on first:**
1. Pods — smallest deployable unit
2. Deployments — manage multiple pod replicas
3. Services — stable network endpoint for pods
4. ConfigMaps and Secrets — configuration and credentials
5. `kubectl` commands — apply, get, describe, logs

**Free interactive labs:**
- https://killercoda.com/playgrounds/scenario/kubernetes — Browser-based K8s playground

### KEDA (Event-Driven Autoscaling)

**Official:**
- https://keda.sh/docs/2.15/concepts/ — How KEDA works
- https://keda.sh/docs/2.15/scalers/rabbitmq-queue/ — RabbitMQ scaler (what this project uses)

**YouTube:**
- "KEDA - Kubernetes Event Driven Autoscaling" by Microsoft Azure — search on YouTube

**Core concept:** KEDA adds a `ScaledObject` CRD (Custom Resource Definition) to Kubernetes. When you create a `ScaledObject`, KEDA watches an external metric (in our case, RabbitMQ queue depth) and automatically scales the target Deployment up or down.

### ArgoCD

**Official:**
- https://argo-cd.readthedocs.io/en/stable/getting_started/ — Getting started
- https://argo-cd.readthedocs.io/en/stable/user-guide/helm/ — Helm integration

**YouTube:**
- "GitOps with ArgoCD" by TechWorld with Nana — https://www.youtube.com/@TechWorldwithNana
- "ArgoCD Tutorial for Beginners" — search on YouTube

### Helm

**Official:**
- https://helm.sh/docs/intro/quickstart/ — Quickstart
- https://helm.sh/docs/chart_template_guide/ — Templating guide (what `{{ .Values.xxx }}` means)

**Core concept:** Helm turns Kubernetes YAML files into templates with variables (using Go templating syntax `{{ }}`). You define values in `values.yaml` and Helm substitutes them when deploying.

### Prometheus

**Official:**
- https://prometheus.io/docs/introduction/overview/
- https://prometheus.io/docs/concepts/metric_types/ — Counter, Gauge, Histogram, Summary

**YouTube:**
- "Prometheus Monitoring Crash Course" by TechWorld with Nana — search on YouTube

---

## 3. Installation — Step by Step

### Option A: Local with Docker Compose (Fastest — No Kubernetes Needed)

#### Step 1 — Install Docker Desktop
Download: https://www.docker.com/products/docker-desktop/

#### Step 2 — Clone the Repository
```powershell
git clone https://github.com/milesbusiness/trading-k8s-platform
cd trading-k8s-platform
```

#### Step 3 — Start All Services
```powershell
docker-compose up
```

Docker Compose will start:
- `order-service` on port 8080
- `risk-service` on port 8081
- `market-data-service` on port 8082
- `settlement-service` on port 8083
- `rabbitmq` with management UI on port 15672

Wait until you see all services print `"Application startup complete."`.

---

### Option B: Deploy to AKS (Full Production Setup)

#### Step 1 — Prerequisites
```powershell
winget install Microsoft.AzureCLI
winget install Helm.Helm
winget install Kubernetes.kubectl

az login
```

#### Step 2 — Create AKS Cluster
```powershell
az group create --name rg-trading-k8s --location westeurope
az aks create `
  --resource-group rg-trading-k8s `
  --name trading-aks `
  --node-count 3 `
  --node-vm-size Standard_D4s_v5 `
  --enable-addons monitoring
az aks get-credentials --resource-group rg-trading-k8s --name trading-aks
```

#### Step 3 — Install KEDA
```powershell
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda --namespace keda --create-namespace
```

Official: https://keda.sh/docs/2.15/deploy/#helm

#### Step 4 — Install ArgoCD
```powershell
helm repo add argo https://argoproj.github.io/argo-helm
helm install argocd argo/argo-cd --namespace argocd --create-namespace

# Get ArgoCD admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

Official: https://argo-cd.readthedocs.io/en/stable/getting_started/

#### Step 5 — Deploy via ArgoCD
```powershell
kubectl apply -f argocd/applications/trading-platform-app.yaml
```

ArgoCD takes over from here — it reads the Helm chart from GitHub and deploys everything.

---

## 4. Project File Structure

```
trading-k8s-platform/
├── services/
│   ├── order-service/
│   │   └── src/main.py           ← Order API: accepts orders, calls risk service
│   ├── risk-service/
│   │   └── src/main.py           ← Risk checks: position limits, notional limits
│   ├── market-data-service/
│   │   └── src/main.py           ← Publishes price ticks to RabbitMQ
│   └── settlement-service/
│       └── src/main.py           ← Processes T+2 settlements, tracks failures
│
├── helm/
│   └── charts/trading-platform/
│       ├── Chart.yaml            ← Chart name and version
│       ├── values.yaml           ← Default configuration for all services
│       └── templates/
│           └── order-service-keda.yaml  ← KEDA ScaledObject for autoscaling
│
├── argocd/
│   └── applications/
│       └── trading-platform-app.yaml   ← ArgoCD Application — tells ArgoCD where to deploy from
│
└── monitoring/
    └── prometheus/
        └── rules/
            └── trading-alerts.yaml      ← Alert rules for Prometheus/Alertmanager
```

---

## 5. Code Walkthrough — Every File Explained

### `services/order-service/src/main.py` — The Order Service

```python
ORDERS_SUBMITTED = Counter("orders_submitted_total", "Total orders submitted", ["status"])
ORDER_LATENCY = Histogram("order_processing_seconds", "Order processing latency",
                           buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5])
```
Prometheus metrics defined at module level (created once). `Counter` only goes up (total orders). `Histogram` records the distribution of values across predefined buckets — the `buckets` list defines cut-off points in seconds (1ms, 5ms, 10ms, 50ms, 100ms, 500ms).

```python
app.mount("/metrics", make_asgi_app())
```
Mounts the Prometheus metrics endpoint at `/metrics`. Prometheus scrapes this URL every 15 seconds. This is how the metrics get into Prometheus.

```python
@app.post("/api/orders", response_model=Order)
async def create_order(request: OrderRequest):
    with ORDER_LATENCY.time():
        # Pre-trade risk check
        async with httpx.AsyncClient(timeout=0.1) as client:    # 100ms timeout
            risk_resp = await client.post(
                f"{RISK_SERVICE_URL}/api/risk/check",
                json={"symbol": request.symbol, "side": request.side, ...}
            )
            risk_approved = risk_resp.json().get("approved", False)
            if not risk_approved:
                ORDERS_SUBMITTED.labels(status="rejected").inc()
                raise HTTPException(400, f"Risk check failed: ...")
```
`with ORDER_LATENCY.time()` — automatically measures how long the block takes and records it in the Histogram. `timeout=0.1` — 100ms hard timeout to the risk service. If risk service takes longer than 100ms, the order is rejected (circuit breaker pattern).

```python
    except httpx.TimeoutException:
        ORDERS_SUBMITTED.labels(status="risk_timeout").inc()
        raise HTTPException(503, "Risk service unavailable — order rejected for capital protection")
```
If the risk service times out, we reject the order and increment the `risk_timeout` counter. This protects against placing orders without risk approval — satisfying MiFID II algorithmic trading controls.

---

### `services/risk-service/src/main.py` — The Risk Service

```python
POSITION_LIMITS = {"EURUSD": 10_000_000, "GBPUSD": 5_000_000, "default": 1_000_000}
TRADER_LIMITS   = {"default_daily_notional": 50_000_000}
positions: dict[str, float] = {}
trader_notional: dict[str, float] = {}
```
In-memory state for the demo. In production, these would be in Redis (sub-millisecond reads, survives service restart). `positions` tracks current net position per symbol; `trader_notional` tracks how much each trader has traded today.

```python
@app.post("/api/risk/check", response_model=RiskCheckResponse)
async def risk_check(request: RiskCheckRequest):
    with CHECK_LATENCY.time():
        # 1. Position limit check
        current_pos = positions.get(request.symbol, 0)
        pos_limit = POSITION_LIMITS.get(request.symbol, POSITION_LIMITS["default"])
        new_pos = current_pos + (request.quantity if request.side == "BUY" else -request.quantity)

        if abs(new_pos) > pos_limit:
            RISK_CHECKS.labels(result="rejected").inc()
            return RiskCheckResponse(approved=False, reason=f"Position limit exceeded: ...")
        checks_passed.append("position_limit")
```
Three checks in sequence:
1. **Position limit** — would this trade exceed the per-symbol position limit?
2. **Trader daily notional** — would this trade exceed the trader's daily trading volume limit?
3. **Concentration** — is this position already at 80%+ of the limit? (warning, not rejection)

If all pass: update the in-memory state and return `approved=True`.

---

### `helm/charts/trading-platform/templates/order-service-keda.yaml` — KEDA Autoscaling

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: order-service-scaler
spec:
  scaleTargetRef:
    name: order-service                          # Which Deployment to scale
  minReplicaCount: {{ .Values.orderService.keda.minReplicas }}   # 0 = scale to zero
  maxReplicaCount: {{ .Values.orderService.keda.maxReplicas }}   # 20 = maximum pods
  cooldownPeriod: 30       # Wait 30s before scaling down (avoid flapping)
  pollingInterval: 5       # Check queue depth every 5 seconds
  triggers:
    - type: rabbitmq
      metadata:
        queueName: {{ .Values.orderService.keda.rabbitmqQueueName }}
        mode: QueueLength
        value: "{{ .Values.orderService.keda.targetQueueLength }}"   # 10 = target msgs per replica
```

`{{ .Values.xxx }}` — Helm template syntax. These values come from `values.yaml`. This means you can change scaling parameters without editing the template — just change `values.yaml`.

`mode: QueueLength` with `value: "10"` means: KEDA targets 10 messages per replica. So:
- 0 messages → 0 replicas
- 10 messages → 1 replica
- 50 messages → 5 replicas
- 200 messages → 20 replicas (capped at maxReplicaCount)

---

### `argocd/applications/trading-platform-app.yaml` — GitOps Declaration

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: trading-platform
  namespace: argocd
spec:
  source:
    repoURL: https://github.com/milesbusiness/trading-k8s-platform
    targetRevision: main
    path: helm/charts/trading-platform
    helm:
      valueFiles:
        - values.yaml
        - values-prod.yaml          # Overrides for production
  destination:
    server: https://kubernetes.default.svc
    namespace: trading
  syncPolicy:
    automated:
      prune: true          # Remove resources no longer in Git
      selfHeal: true       # Revert manual changes to the cluster
      allowEmpty: false    # Never deploy an empty application
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m    # Exponential backoff: 5s, 10s, 20s, 40s, 80s
```

`selfHeal: true` — this is the key setting. If anyone runs `kubectl edit deployment order-service` to manually change something, ArgoCD will detect the drift within 3 minutes and reset it back to what Git says. Production environment is protected from ad-hoc changes.

---

### `monitoring/prometheus/rules/trading-alerts.yaml` — Alerting Rules

```yaml
- alert: OrderServiceHighLatency
  expr: histogram_quantile(0.99, rate(order_processing_seconds_bucket[5m])) > 0.1
  for: 2m
```
**Explanation of the expression:**
- `order_processing_seconds_bucket` — the Histogram metric from the order service
- `rate(...[5m])` — rate of change over the last 5 minutes
- `histogram_quantile(0.99, ...)` — calculate the 99th percentile from the histogram buckets
- `> 0.1` — threshold: 100ms

`for: 2m` — the condition must be true for 2 consecutive minutes before the alert fires (prevents false positives from brief spikes).

```yaml
- alert: RiskServiceDown
  expr: up{job="risk-service"} == 0
  for: 30s
  labels:
    severity: critical
    page: "true"
```
`up{job="risk-service"}` is a Prometheus built-in metric that is `1` when the target is reachable and `0` when it is not. After 30 seconds of the risk service being unreachable, a `critical` alert fires and pages on-call.

```yaml
- alert: HighSettlementFailureRate
  expr: rate(settlements_failed_total[5m]) / rate(settlements_created_total[5m]) > 0.001
```
This calculates the ratio of failed settlements to total settlements over 5 minutes. `0.001` = 0.1% — the CSDR Article 7 regulatory threshold.

---

## 6. How to Run and View Output

### With Docker Compose (Local)

```powershell
docker-compose up
```

#### Test the Full Order Flow

```powershell
# 1. Submit an order (triggers automatic risk check to risk-service)
Invoke-RestMethod -Method Post -Uri "http://localhost:8080/api/orders" `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"symbol":"EURUSD","side":"BUY","quantity":100000,"trader_id":"trader-1"}'
```

Expected response:
```json
{
  "order_id": "3f7a2c1b-...",
  "symbol": "EURUSD",
  "side": "BUY",
  "quantity": 100000,
  "status": "ACCEPTED",
  "risk_approved": true,
  "created_at": "2026-06-22T..."
}
```

```powershell
# 2. Check current risk positions
Invoke-RestMethod http://localhost:8081/api/risk/positions
# {"positions": {"EURUSD": 100000}}

# 3. Try to exceed position limit (EURUSD limit is 10,000,000)
# Submit orders until you hit the limit and get a 400 rejection

# 4. View Prometheus metrics (raw text format)
Invoke-RestMethod http://localhost:8080/metrics
# Look for: orders_submitted_total{status="accepted"} 1
#           order_processing_seconds_bucket{le="0.1"} 1
```

#### RabbitMQ Management UI

Open in browser: **http://localhost:15672**
- Username: `guest`
- Password: `guest`

You can see the `orders` queue depth here — this is what KEDA would watch in a Kubernetes deployment.

#### API Documentation

- Order Service: http://localhost:8080/docs
- Risk Service: http://localhost:8081/docs
- Market Data Service: http://localhost:8082/docs
- Settlement Service: http://localhost:8083/docs

### Viewing Prometheus Metrics (Kubernetes)

After AKS deployment:
```powershell
# Port-forward Prometheus to localhost
kubectl port-forward svc/prometheus 9090:9090 -n monitoring

# Open Prometheus query UI
# Browser: http://localhost:9090
```

Useful PromQL queries to run in the UI:
```promql
# P99 order latency (last 5 minutes)
histogram_quantile(0.99, rate(order_processing_seconds_bucket[5m]))

# Orders accepted vs rejected
rate(orders_submitted_total{status="accepted"}[5m])
rate(orders_submitted_total{status="rejected"}[5m])

# Risk check approval rate
rate(risk_checks_total{result="approved"}[5m])
```

### Viewing ArgoCD (Kubernetes)

```powershell
kubectl port-forward svc/argocd-server 8080:443 -n argocd

# Open in browser: https://localhost:8080
# Login: admin / (password from earlier step)
```

You will see the `trading-platform` application with a visual tree of all deployed resources and their sync status.

---

## Common Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| Order rejected with "Risk service unavailable" | Risk service container not started yet | Wait for all containers to be healthy; Docker Compose starts them in parallel |
| `docker-compose up` fails with port conflict | Something else using port 8080 | Change `ports:` in `docker-compose.yml` |
| KEDA not scaling | RabbitMQ secret `rabbitmq-secret` missing in cluster | Create the secret: `kubectl create secret generic rabbitmq-secret --from-literal=amqp-uri=amqp://guest:guest@rabbitmq:5672` |
| ArgoCD shows "OutOfSync" | Helm chart was changed locally but not pushed to Git | ArgoCD syncs from Git, not local files — push your changes |
