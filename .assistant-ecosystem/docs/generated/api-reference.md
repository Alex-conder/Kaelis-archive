# OpenClaw Assistant API Reference

Generated: 2026-03-16 20:03:09

## Tools Overview

Total: 30 tools
### ai-manager

**File**: ai-manager.ps1

AI Model Manager for OpenClaw Assistant
.DESCRIPTION
    Multi-model switching, load balancing, cost tracking

Multi-model switching, load balancing, cost tracking

---

### alert-manager

**File**: alert-manager.ps1

Smart Alert Manager for OpenClaw Assistant
.DESCRIPTION
    Intelligent alert rules, suppression, escalation, multi-channel notifications

Intelligent alert rules, suppression, escalation, multi-channel notifications

---

### api-gateway

**File**: api-gateway.ps1

API Gateway Manager for OpenClaw Assistant
.DESCRIPTION
    Route management, rate limiting, authentication and authorization

Route management, rate limiting, authentication and authorization

---

### assistant

**File**: assistant.ps1

OpenClaw Assistant Ecosystem Management Script
.DESCRIPTION
    Unified management for .openclaw (user install) and OpenClawAssistant (dev) 
    Provides unified CLI to start, manage and sync components
.PARAMETER Command
    Command to execute: start, stop, status, sync, config, logs, clean, doctor, init
.PARAMETER Component
    Component name: gateway, backend, desktop, react, cli, all
.PARAMETER Profile
    Profile: default, dev, production
.EXAMPLE
    ./assistant.ps1 start gateway
    ./assistant.ps1 status
    ./assistant.ps1 sync config

Unified management for .openclaw (user install) and OpenClawAssistant (dev) 
    Provides unified CLI to start, manage and sync components
.PARAMETER Command
    Command to execute: start, stop, status, sync, config, logs, clean, doctor, init
.PARAMETER Component
    Component name: gateway, backend, desktop, react, cli, all
.PARAMETER Profile
    Profile: default, dev, production
.EXAMPLE
    ./assistant.ps1 start gateway
    ./assistant.ps1 status
    ./assistant.ps1 sync config

---

### assistant-cli

**File**: assistant-cli.ps1

Interactive CLI for OpenClaw Assistant Ecosystem
.DESCRIPTION
    Command-line interface with autocomplete, history, and shortcuts

Command-line interface with autocomplete, history, and shortcuts

---

### backup-manager

**File**: backup-manager.ps1

Backup and Recovery Manager for OpenClaw Assistant
.DESCRIPTION
    Automated backup, version control, disaster recovery

Automated backup, version control, disaster recovery

---

### chaos-engineering

**File**: chaos-engineering.ps1

Chaos Engineering Tool for OpenClaw Assistant
.DESCRIPTION
    Fault injection, resilience testing, recovery verification

Fault injection, resilience testing, recovery verification

---

### cluster-manager

**File**: cluster-manager.ps1

Cluster Manager for OpenClaw Assistant
.DESCRIPTION
    Multi-node management, distributed deployment, load balancing

Multi-node management, distributed deployment, load balancing

---

### completion

**File**: completion.ps1

Command Auto-Completion for OpenClaw Assistant
.DESCRIPTION
    Tab completion, parameter hints, command history

Tab completion, parameter hints, command history

---

### config-versioning

**File**: config-versioning.ps1

Configuration Version Control for OpenClaw Assistant
.DESCRIPTION
    Git integration, config history, rollback functionality

Git integration, config history, rollback functionality

---

### cost-optimizer

**File**: cost-optimizer.ps1

Cost Optimizer for OpenClaw Assistant
.DESCRIPTION
    Resource cost analysis, optimization recommendations, budget management

Resource cost analysis, optimization recommendations, budget management

---

### create-shortcuts

**File**: create-shortcuts.ps1

Create shortcuts for OpenClaw Assistant Ecosystem
.DESCRIPTION
    Creates desktop shortcuts, Start Menu entries, and context menu items
.PARAMETER All
    Create all types of shortcuts

Creates desktop shortcuts, Start Menu entries, and context menu items
.PARAMETER All
    Create all types of shortcuts

---

### dashboard-server

**File**: dashboard-server.ps1

Dashboard Web Server for OpenClaw Assistant
.DESCRIPTION
    Serves the web dashboard for monitoring and control

Serves the web dashboard for monitoring and control

---

### data-migrator

**File**: data-migrator.ps1

鏁版嵁杩佺Щ宸ュ叿 - Data Migrator for OpenClaw Assistant
.DESCRIPTION
    鏁版嵁澶囦唤銆佽縼绉汇€佸悓姝ャ€佺増鏈崌绾?

鏁版嵁澶囦唤銆佽縼绉汇€佸悓姝ャ€佺増鏈崌绾?

---

### diagnostics

**File**: diagnostics.ps1

System Diagnostics Tool for OpenClaw Assistant
.DESCRIPTION
    Deep diagnostics, problem identification, repair suggestions

Deep diagnostics, problem identification, repair suggestions

---

### doc-builder

**File**: doc-builder.ps1

Documentation Builder for OpenClaw Assistant
.DESCRIPTION
    Generate API docs, config docs, and operation manuals

Generate API docs, config docs, and operation manuals

---

### health-probe

**File**: health-probe.ps1

Health Check Probe for OpenClaw Assistant
.DESCRIPTION
    HTTP probes, custom checks, status aggregation

HTTP probes, custom checks, status aggregation

---

### log-analyzer

**File**: log-analyzer.ps1

Log Analysis Engine for OpenClaw Assistant
.DESCRIPTION
    Log aggregation, pattern recognition, anomaly detection

Log aggregation, pattern recognition, anomaly detection

---

### metrics-exporter

**File**: metrics-exporter.ps1

Metrics Exporter for OpenClaw Assistant
.DESCRIPTION
    Prometheus format, time series data, visualization

Prometheus format, time series data, visualization

---

### monitor-service

**File**: monitor-service.ps1

OpenClaw Assistant Service Monitor
.DESCRIPTION
    Background service monitor that checks component health and auto-restarts failed services
.PARAMETER Interval
    Check interval in seconds (default: 30)
.PARAMETER LogFile
    Path to log file

Background service monitor that checks component health and auto-restarts failed services
.PARAMETER Interval
    Check interval in seconds (default: 30)
.PARAMETER LogFile
    Path to log file

---

### notifier

**File**: notifier.ps1

Smart Notification System for OpenClaw Assistant
.DESCRIPTION
    Email, desktop, and webhook notifications

Email, desktop, and webhook notifications

---

### optimizer

**File**: optimizer.ps1

Performance Optimizer for OpenClaw Assistant
.DESCRIPTION
    Cache management, resource cleanup, performance analysis

Cache management, resource cleanup, performance analysis

---

### profiler

**File**: profiler.ps1

鎬ц兘鍓栨瀽鍣?- Profiler for OpenClaw Assistant
.DESCRIPTION
    CPU鍓栨瀽銆佸唴瀛樺垎鏋愩€佽皟鐢ㄩ摼杩借釜銆佹€ц兘鎶ュ憡鐢熸垚

CPU鍓栨瀽銆佸唴瀛樺垎鏋愩€佽皟鐢ㄩ摼杩借釜銆佹€ц兘鎶ュ憡鐢熸垚

---

### remote-manager

**File**: remote-manager.ps1

Remote Management for OpenClaw Assistant
.DESCRIPTION
    SSH management, remote control, secure tunnel

SSH management, remote control, secure tunnel

---

### resource-quota

**File**: resource-quota.ps1

Resource Quota Manager for OpenClaw Assistant
.DESCRIPTION
    CPU/Memory limits, usage quotas, alert thresholds

CPU/Memory limits, usage quotas, alert thresholds

---

### role-switcher

**File**: role-switcher.ps1

Role Switcher for OpenClaw Assistant
.DESCRIPTION
    Switch between different user roles: Admin, Developer, User, DevOps, Analyst

Switch between different user roles: Admin, Developer, User, DevOps, Analyst

---

### service-mesh

**File**: service-mesh.ps1

Service Mesh Manager for OpenClaw Assistant
.DESCRIPTION
    Traffic routing, load balancing, circuit breaker, service discovery

Traffic routing, load balancing, circuit breaker, service discovery

---

### sync-config

**File**: sync-config.ps1

Configuration Synchronization Script
.DESCRIPTION
    Synchronizes configuration between .openclaw and OpenClawAssistant environments
.PARAMETER Direction
    Sync direction: user-to-dev, dev-to-user, bidirectional
.PARAMETER WhatIf
    Show what would be synced without making changes

Synchronizes configuration between .openclaw and OpenClawAssistant environments
.PARAMETER Direction
    Sync direction: user-to-dev, dev-to-user, bidirectional
.PARAMETER WhatIf
    Show what would be synced without making changes

---

### test-runner

**File**: test-runner.ps1

Test Runner for OpenClaw Assistant
.DESCRIPTION
    Simple test execution and reporting

Simple test execution and reporting

---

### tray-app

**File**: tray-app.ps1

System Tray Application for OpenClaw Assistant
.DESCRIPTION
    Background runner, quick menu, status indicator

Background runner, quick menu, status indicator

---


