# Development Guide

## Prerequisites

- Python 3.12
- Docker + Docker Compose
- kubectl (for AKS)
- Helm 3.16+
- ArgoCD CLI (optional)

## Local Development (Docker Compose)

```bash
git clone https://github.com/milesbusiness/trading-k8s-platform
cd trading-k8s-platform

docker-compose up
```

Services available at:
- `http://localhost:8080` — market-data-service
- `http://localhost:8081` — order-service
- `http://localhost:8082` — risk-service
- `http://localhost:8083` — settlement-service
- `http://localhost:15672` — RabbitMQ management UI

## Run a Single Service

```bash
cd services/order-service/src
pip install fastapi uvicorn httpx prometheus-client pydantic
uvicorn main:app --port 8081 --reload
```

## Try the Order Flow

```bash
# 1. Submit an order (triggers risk check)
curl -X POST http://localhost:8081/api/orders \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EURUSD","side":"BUY","quantity":100000,"trader_id":"t1"}'

# 2. Check risk positions
curl http://localhost:8082/api/risk/positions

# 3. Create settlement
curl -X POST "http://localhost:8083/api/settlement?order_id=abc&symbol=EURUSD&quantity=100000"

# 4. Check Prometheus metrics
curl http://localhost:8081/metrics | grep orders_submitted
```

## Deploy to AKS

```bash
# 1. Connect to AKS
az aks get-credentials --resource-group rg-trading --name trading-prod-aks

# 2. Install KEDA
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda -n keda --create-namespace

# 3. Install ArgoCD
helm repo add argo https://argoproj.github.io/argo-helm
helm install argocd argo/argo-cd -n argocd --create-namespace

# 4. Apply ArgoCD app (GitOps takes over from here)
kubectl apply -f argocd/applications/trading-platform-app.yaml
```

## Build and Push Images

```bash
docker build -t ghcr.io/milesbusiness/trading-k8s-platform/market-data-service:latest \
  services/market-data-service/
docker push ghcr.io/milesbusiness/trading-k8s-platform/market-data-service:latest
```

CI does this automatically on push to `main`.

## Project Structure

```
trading-k8s-platform/
├── services/
│   ├── market-data-service/src/main.py
│   ├── order-service/src/main.py
│   ├── risk-service/src/main.py
│   └── settlement-service/src/main.py
├── helm/charts/trading-platform/
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
├── argocd/applications/
│   └── trading-platform-app.yaml
├── monitoring/
│   ├── prometheus/rules/trading-alerts.yaml
│   └── grafana/dashboards/
└── .github/workflows/ci.yml
```
