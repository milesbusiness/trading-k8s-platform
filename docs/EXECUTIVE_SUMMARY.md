# Executive Summary — Trading K8s Platform

## Business Problem

A trading firm's technology platform must solve a set of requirements that are fundamentally in tension:

**Availability vs. Cost** — The risk system must never go down, yet paying for 20 order-processing servers during quiet overnight hours wastes money. Both must be true simultaneously.

**Speed of deployment vs. Risk of change** — Trading platforms cannot be taken offline during market hours for upgrades. Every change must happen invisibly, while the system continues serving live orders.

**Performance monitoring vs. Regulatory compliance** — MiFID II Article 17 requires investment firms to monitor their algorithmic trading systems in real-time and maintain circuit breakers. This is not optional — it is a licence condition.

Traditional approaches resolve these tensions by picking one: either over-provision for availability, or accept downtime for upgrades, or address compliance separately as an afterthought. This platform demonstrates how all three can be achieved simultaneously.

## The Solution

A production-grade Kubernetes platform running four independent trading microservices on Azure AKS, with:
- **Event-driven autoscaling** (KEDA) — services scale from zero replicas during quiet periods to 20 under peak load
- **Zero-downtime deployments** via GitOps (ArgoCD) — every code change is deployed while the system continues serving traffic
- **Built-in regulatory monitoring** — Prometheus metrics and alerts aligned to MiFID II Article 17 and CSDR Article 7

## The Four Services (Non-Technical Summary)

**Market Data Service** — Continuously receives price feeds from external sources (foreign exchange rates, equity prices) and distributes them internally. Always on, 2 servers.

**Order Service** — The front door for trade orders. Every order passes through a risk check before being accepted. Automatically scales up during busy periods and back down when quiet — from zero servers to 20, driven by actual workload.

**Risk Service** — Checks every single trade order against position limits in under 5 milliseconds before it is allowed to proceed. Never allowed to be fully offline — a mandatory minimum of 2 servers is enforced at all times, even during routine maintenance. This is the most critical service on the platform.

**Settlement Service** — After a trade is executed, this service generates settlement instructions and tracks whether they complete on time (T+2). It reports settlement failure rates for CSDR regulatory compliance.

## Cost Efficiency

The key innovation is the Order Service autoscaling:

| Market Condition | Server Count | Hourly Cost (approx.) |
|-----------------|-------------|----------------------|
| Market closed, no orders | 0 servers | €0.00 |
| Light activity (10 orders/min) | 1 server | ~€0.40 |
| Normal trading session | 5 servers | ~€2.00 |
| Peak open/close period | 20 servers | ~€8.00 |

**Result:** 60–70% reduction in Order Service compute costs compared to always-on provisioning at peak capacity.

## Regulatory Compliance

| Regulation | Requirement | Implementation |
|-----------|-------------|----------------|
| MiFID II Art. 17 | Monitor algorithmic trading systems | P99 latency alert triggers if order processing exceeds 100ms |
| MiFID II Art. 17 | Automated circuit breakers | Risk Service outage alert triggers immediate action |
| CSDR Art. 7 | Track settlement failure rates | Settlement failure alert if rate exceeds 0.1% |

## Deployment Safety

**The problem with manual deployment:** A developer types `kubectl apply` in the wrong terminal and accidentally deploys development code to production. This happens.

**The solution:** ArgoCD enforces that production can only ever match what is in Git. If someone manually changes something in the production cluster, ArgoCD detects the discrepancy and reverts it within 3 minutes. Every production change is traceable to a Git commit, with author and timestamp.

## Infrastructure Costs

| Service | Specification | Monthly Cost (approx.) |
|---------|--------------|----------------------|
| Azure AKS | 3-node cluster, Standard_D4s_v5, 3 AZs | ~€900 |
| Azure SQL | Settlement database, Business Critical | ~€400 |
| RabbitMQ (3-node) | Self-managed on AKS | Included in AKS |
| Azure Application Gateway | WAF_v2 | ~€200 |
| Azure Monitor + Alertmanager | Standard | ~€100 |
| **Total** | | **~€1,600/month** |

## Stakeholders

| Stakeholder | What They Gain |
|-------------|---------------|
| Head of Technology | Proven ability to deploy during market hours without risk |
| Chief Risk Officer | MiFID II circuit breaker alerting built into infrastructure |
| Chief Financial Officer | Automatic cost reduction during off-peak hours |
| Compliance Team | CSDR settlement failure alerts and reporting |
| Engineering Lead | GitOps — no manual production changes, full audit trail |

## Summary

This platform demonstrates that the fundamental tensions of trading technology — availability vs. cost, deployment speed vs. risk, performance vs. compliance — can be resolved simultaneously using modern Kubernetes architecture.

Key outcomes: 60–70% compute cost reduction during off-peak hours; zero-downtime deployments during live trading; MiFID II and CSDR monitoring built in from day one.

---

*Author: Dilip Kumar Jena | Platform: Azure AKS + KEDA + ArgoCD | Regulation: MiFID II, CSDR*
