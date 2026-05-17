# 📊 Prometheus-Grafana Monitoring Stack

A production-style monitoring and alerting platform built with Prometheus, Grafana, Alertmanager, Node Exporter, Intel GPU Exporter, NVIDIA DCGM Exporter, and a custom Flask application.

---

# 📌 Overview

This project provides a complete observability stack using Docker Compose.

The environment includes:

- 📈 Metrics collection with Prometheus
- 📊 Visualization dashboards with Grafana
- 🚨 Centralized alerting with Alertmanager
- 🖥️ Host monitoring with Node Exporter
- 🎮 Intel GPU monitoring
- ⚡ NVIDIA GPU monitoring
- 🧪 Custom Flask metrics application
- 🔔 Slack notification integration
- 🐳 Fully containerized deployment

Designed for real-world infrastructure monitoring and production-style observability environments.

---

# 🚀 Features

| Feature | Description |
|---|---|
| 📈 Real-Time Monitoring | Live infrastructure & application metrics |
| 🚨 Advanced Alerting | Alertmanager with routing & inhibition |
| 📊 Grafana Dashboards | Full visualization platform |
| 🖥️ Node Exporter | CPU, RAM, disk & network monitoring |
| 🎮 Intel GPU Monitoring | Intel GPU metrics via exporter |
| ⚡ NVIDIA GPU Monitoring | DCGM exporter for NVIDIA GPUs |
| 🧠 Recording Rules | Precomputed Prometheus metrics |
| 🔔 Slack Notifications | Real-time alert delivery |
| 🐳 Dockerized Stack | One-command deployment |
| 📦 Persistent Storage | Volumes preserve monitoring data |

---

# 🏗️ Architecture

```text
┌──────────────────────────────────────────────────────┐
│                    Monitoring Stack                  │
│                                                      │
│  ┌──────────────┐        scrape       ┌───────────┐ │
│  │   My Flask   │◄───────────────────│           │ │
│  │     App      │                    │           │ │
│  └──────────────┘                    │           │ │
│                                      │           │ │
│  ┌──────────────┐        scrape      │           │ │
│  │ NodeExporter │◄───────────────────│           │ │
│  └──────────────┘                    │           │ │
│                                      │PROMETHEUS│ │
│  ┌──────────────┐        scrape      │   :9090  │ │
│  │ Intel GPU    │◄───────────────────│           │ │
│  │  Exporter    │                    │           │ │
│  └──────────────┘                    │           │ │
│                                      │           │ │
│  ┌──────────────┐        scrape      │           │ │
│  │ DCGM Exporter│◄───────────────────│           │ │
│  │ NVIDIA GPUs  │                    └─────┬─────┘ │
│  └──────────────┘                          │       │
│                                            ▼       │
│                                   ┌─────────────┐ │
│                                   │Alertmanager│ │
│                                   │   :9093    │ │
│                                   └─────┬─────┘ │
│                                         ▼       │
│                                  Slack Alerts   │
│                                                 │
│                 query                           │
│  ┌──────────────┐◄─────────────────────────────┐│
│  │   Grafana    │                              ││
│  │    :3000     │                              ││
│  └──────────────┘                              ││
└──────────────────────────────────────────────────────┘
```

---

# 📂 Project Structure

```text
monitoring-stack/
│
├── docker-compose.yml
├── prometheus.yml
├── alertmanager.yml
├── alert.rules.yml
│
├── app/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py

```

---

# ⚡ Quick Start

## 1️⃣ Clone Repository

```bash
git clone https://github.com/N1N0u/PcMonitor.git
cd PcMonitor
```

## 2️⃣ Start the Entire Stack

```bash
docker compose up -d
```

## 3️⃣ Verify Containers

```bash
docker compose ps
```

Wait around 30 seconds for all services to initialize.

---

# 🌐 Service URLs

| Service | URL |
|---|---|
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| Alertmanager | http://localhost:9093 |
| Node Exporter | http://localhost:9100/metrics |
| Intel GPU Exporter | http://localhost:8686/metrics |
| NVIDIA DCGM Exporter | http://localhost:9400/metrics |
| Flask App | http://localhost:5000 |

---

# 🔑 Grafana Credentials

```text
Username: admin
Password: admin123
```

---

# 🐳 Services Included

| Service | Purpose |
|---|---|
| Prometheus | Metrics collection & TSDB |
| Grafana | Visualization dashboards |
| Alertmanager | Alert routing & notifications |
| Node Exporter | System metrics |
| Intel GPU Exporter | Intel GPU telemetry |
| DCGM Exporter | NVIDIA GPU telemetry |
| Flask App | Custom Stress CPU-GPU-RAM |

---

# 📈 Prometheus Configuration Highlights

## Scrape Targets

The stack automatically monitors:

- Prometheus
- Node Exporter
- Alertmanager
- Grafana
- Flask Application
- Intel GPU Exporter
- NVIDIA DCGM Exporter

---

## Recording Rules

Precomputed metrics include:

```promql
instance:cpu_usage_percent
instance:memory_usage_percent
instance:disk_usage_percent
app:error_rate_percent
app:request_latency_p95
app:request_rate_per_second
```

These optimize dashboard performance and reduce query complexity.

---

# 🚨 Alerting System

## Infrastructure Alerts

| Alert | Trigger |
|---|---|
| InstanceDown | Service unavailable |
| HighCpuUsage | CPU > 85% |
| CriticalCpuUsage | CPU > 95% |
| LowMemory | RAM usage critical |
| LowDiskSpace | Disk > 80% |
| CriticalDiskSpace | Disk > 95% |

---

## Application Alerts

| Alert | Trigger |
|---|---|
| HighErrorRate | Error rate > 5% |
| HighP95Latency | Latency > 500ms |
| LowRequestRate | Very low traffic |

---

## Prometheus Self Monitoring

The stack also monitors Prometheus itself:

- Failed config reloads
- TSDB issues
- Slow scrape operations

---


# 📊 Grafana Setup

## Add Prometheus Data Source

```text
http://prometheus:9090
```

---
# 🧠 Useful PromQL Queries

## CPU Usage %

```promql
100 - (
  avg by(instance)(
    irate(node_cpu_seconds_total{mode="idle"}[5m])
  ) * 100
)
```

## Memory Usage %

```promql
100 - (
  node_memory_MemAvailable_bytes
  /
  node_memory_MemTotal_bytes * 100
)
```

## Disk Usage %

```promql
100 - (
  node_filesystem_avail_bytes{mountpoint="/"}
  /
  node_filesystem_size_bytes{mountpoint="/"} * 100
)
```

## Error Rate %

```promql
app:error_rate_percent
```

## p95 Request Latency

```promql
app:request_latency_p95
```

## Intel GPU Metrics

```promql
intel_gpu_power_watts
```

## NVIDIA GPU Metrics

```promql
DCGM_FI_DEV_GPU_UTIL
```

---

# 🛠️ Useful Commands

## Start Stack

```bash
docker compose up -d
```

## View Logs

```bash
docker compose logs -f prometheus
```

## Restart Prometheus

```bash
docker compose restart prometheus
```

## Remove Everything

```bash
docker compose down -v
```

---

# 🔍 Troubleshooting

## Check Containers

```bash
docker compose ps
```

## Verify Targets

Open:

```text
http://localhost:9090/targets
```

All targets should show:

```text
UP
```

---

## Intel GPU Exporter Not Working?

```bash
ls /dev/dri
```

---

## NVIDIA GPU Exporter Not Working?

```bash
nvidia-smi
```

---

# ⚡ Stack Capabilities

| Capability | Status |
|---|---|
| Production-Oriented | ✅ |
| GPU Monitoring | ✅ |
| Alert Automation | ✅ |
| Dockerized | ✅ |
| Real-Time Metrics | ✅ |
| Persistent Storage | ✅ |

---

# 👤 Author

**ALIAT Atef**

---

# ⭐ Final Statement

This project demonstrates the ability to:

- Build complete observability stacks
- Configure advanced Prometheus setups
- Design scalable alerting systems
- Monitor infrastructure and GPUs
- Deploy production-style monitoring environments
