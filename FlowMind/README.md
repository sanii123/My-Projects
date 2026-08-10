# FlowMind — Smart Elevator & Escalator Management System

> **TIES454 — Agent Technologies for Developers**
> University of Jyväskylä | April 2026


---

## Overview

FlowMind is a **Multi-Agent System (MAS)** built with the SPADE framework that addresses a fundamental gap in modern building infrastructure management. Today, elevators and escalators are monitored reactively — faults are detected late, data is siloed, and maintenance decisions are made manually without real-time context.

FlowMind introduces a coordinated, reasoning layer that:
- Continuously monitors IoT sensor streams from elevators and escalators
- Detects and diagnoses faults before they cause failures
- Understands the human context of passenger demand
- Autonomously dispatches the right technician at the right time
- Generates plain-language shift reports for building managers

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FlowMind MAS                              │
│                                                             │
│  ┌──────────────┐     fault_signature    ┌───────────────┐  │
│  │ Fault        │ ──────────────────────▶│ Diagnostic    │  │
│  │ Detection    │                         │ Agent         │  │
│  │ Agent (0..*) │ ──── fault_alert ──────▶│               │  │
│  └──────────────┘                         └───────┬───────┘  │
│                                                   │          │
│  ┌──────────────┐                                 │ diagnostic_report
│  │ People Flow  │ ──── demand_forecast ───────────┤          │
│  │ Predictor    │                                 │          │
│  │ Agent  (1)   │                         ┌───────▼───────┐  │
│  └──────────────┘                         │ Dispatch      │  │
│                                           │ Coordinator   │  │
│                                           │ Agent   (1)   │  │
│                                           └───────┬───────┘  │
│                                                   │          │
│                                         work_order│          │
│                                                   ▼          │
│                                           ┌───────────────┐  │
│                                           │ Reporting     │  │
│                                           │ Agent   (1)   │  │
│                                           └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Agents

| Agent | Cardinality | Role |
|---|---|---|
| **Fault Detection Agent** | 0..* | Monitors IoT sensor streams, detects anomalies, classifies severity |
| **Diagnostic Agent** | 0..* | Root-cause analysis, time-to-failure estimation |
| **People Flow Predictor** | 1 | Passenger demand forecasting using time-of-day and calendar context |
| **Dispatch Coordinator** | 1 | Central triage authority — urgency classification and technician dispatch |
| **Reporting Agent** | 1 | End-of-shift operational summaries for building managers |

---

## Technology Stack

| Component | Technology |
|---|---|
| Agent Framework | [SPADE 3.x](https://spade-mas.readthedocs.io/) |
| Messaging Protocol | XMPP (ejabberd via Docker) |
| Agent Communication | ACL-style messages with ontology metadata |
| Dashboard Backend | Flask REST API |
| Dashboard Frontend | HTML / CSS / JavaScript |
| Language | Python 3.11 |

---

## Project Structure

```
flowmind-mas/
├── agents/
│   ├── fault_detection_agent.py       # IoT sensor monitoring + anomaly detection
│   ├── diagnostic_agent.py            # Root cause analysis + TTF estimation
│   ├── people_flow_agent.py           # Passenger demand forecasting
│   ├── dispatch_coordinator_agent.py  # Triage + technician dispatch
│   └── reporting_agent.py            # Shift report generation
├── config/
│   └── settings.py                    # Agent JIDs, thresholds, equipment list
├── utils/
│   ├── sensor_simulator.py            # Simulated IoT sensor data
│   ├── message_templates.py           # Standardized ACL message builders
│   ├── event_store.py                 # Thread-safe shared in-memory store
│   └── dashboard_server.py           # Flask REST API server
├── dashboard.html                     # Real-time operations dashboard
├── main.py                            # System entry point
├── requirements.txt                   # Python dependencies
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker Desktop (for XMPP server)

### 1. Clone the Repository

```bash
git clone
cd flowmind-mas
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Start XMPP Server (Docker)

```bash
docker run -d --name ejabberd \
  -p 5222:5222 -p 5269:5269 -p 5280:5280 \
  -e CTL_ON_CREATE="register admin localhost adminpass" \
  ejabberd/ecs
```

### 5. Register Agent Accounts

```bash
docker exec ejabberd bin/ejabberdctl register fault_detection localhost spade
docker exec ejabberd bin/ejabberdctl register diagnostic localhost spade
docker exec ejabberd bin/ejabberdctl register people_flow localhost spade
docker exec ejabberd bin/ejabberdctl register dispatch localhost spade
docker exec ejabberd bin/ejabberdctl register reporting localhost spade
```

### 6. Run the System

```bash
python main.py
```

### 7. Open the Dashboard

Open `dashboard.html` in your browser (Chrome or Firefox).

The dashboard connects to `http://localhost:5000/api/snapshot` and updates every second.

---

## Dashboard

The real-time operations dashboard provides:

- **Agent Network** — Live status and message count for all 5 agents
- **Equipment Monitoring** — Sensor readings (vibration, temperature, door cycles) for all units
- **Incident Log** — All dispatched work orders with urgency, root cause, and technician
- **Agent Message Feed** — Live inter-agent communication stream
- **Passenger Demand Forecast** — Real-time output from People Flow Predictor
- **KPI Summary** — Total incidents, emergencies, minutes of downtime prevented

---

## Agent Communication Flow

### Scenario 1 — Rush-Hour Fault (Helsinki Office Tower)

```
08:42 — Fault Detection Agent detects bearing wear on ELV-04
      → Sends fault_signature to Diagnostic Agent
      → Sends fault_alert to Dispatch Coordinator

        Diagnostic Agent analyses fault
      → Cross-references failure pattern DB
      → Estimates TTF: 1.1 hours (EMERGENCY)
      → Sends diagnostic_report to Dispatch Coordinator

        People Flow Predictor reports 340 passengers expected
      → Sends demand_forecast to Dispatch Coordinator

        Dispatch Coordinator combines all three inputs
      → Classifies urgency: EMERGENCY
      → Selects technician: Mikael Virtanen (Helsinki CBD)
      → Issues work_order to Reporting Agent

08:58 — Technician arrives before peak load
        Reporting Agent logs incident in shift summary
```

### Scenario 2 — Cascading Fault (Shopping Mall)

```
Two Fault Detection Agent instances detect simultaneous faults
Two Diagnostic Agent instances run in parallel
Dispatch Coordinator performs comparative triage
→ Emergency dispatch for obstruction (ESC-A)
→ Scheduled inspection for motor issue (ESC-B)
Both escalators restored within 90 minutes
```

---

## Autonomous Agent Decisions

Each agent makes at least one independent decision:

| Agent | Autonomous Decision |
|---|---|
| Fault Detection | Severity classification (low / medium / high) based on sensor thresholds |
| Diagnostic | Root cause identification from failure pattern knowledge base |
| Diagnostic | Time-to-failure estimation adjusted by severity multiplier |
| People Flow | Demand risk assessment (low / medium / high) from passenger count |
| Dispatch Coordinator | Urgency classification combining TTF + demand risk |
| Dispatch Coordinator | Technician selection based on equipment type and speciality |
| Reporting Agent | KPI computation — downtime avoided, faults resolved |

---

## Equipment Monitored

| ID | Type | Location |
|---|---|---|
| ELV-01 | Elevator | Helsinki Tower, Floors 1–22 |
| ELV-04 | Elevator | Helsinki Tower, Floors 1–22 |
| ESC-A | Escalator | Mall, North Wing |
| ESC-B | Escalator | Mall, South Wing |

---

## Fault Thresholds

| Sensor | Warning | Critical |
|---|---|---|
| Vibration | > 5.0 | > 7.0 |
| Temperature (°C) | > 65.0 | > 75.0 |
| Door Cycles | > 800 | > 950 |

---

## Message Ontologies

| Ontology | Sender | Receiver | Purpose |
|---|---|---|---|
| `fault-detection` | Fault Detection | Diagnostic | Fault signature with sensor values |
| `fault-alert` | Fault Detection | Dispatch | Initial anomaly notification |
| `diagnostic-report` | Diagnostic | Dispatch | Root cause + TTF + action category |
| `demand-forecast` | People Flow | Dispatch | Passenger count + risk level |
| `dispatch-decision` | Dispatch | Reporting | Work order + technician briefing |

---

## API Endpoints

The Flask server exposes the following endpoints:

| Endpoint | Description |
|---|---|
| `GET /api/snapshot` | Full system state (used by dashboard) |
| `GET /api/agents` | Agent status and message counts |
| `GET /api/incidents` | Incident log |
| `GET /api/kpis` | KPI counters |
| `GET /api/health` | Health check |

---

## Design Methodology

This system was designed using the **Gaia Agent-Oriented Software Engineering (AOSE)** methodology, covering:

- Environmental model (resources: sensor streams, maintenance logs, demand forecasts)
- Preliminary role and interaction models (two usage scenarios)
- Role schemas (liveness and safety properties for all five agents)
- Agent model with cardinality rationale
- Service models (pre/post-conditions for all services)

See `FlowMind_Gaia_Assignment_1.pdf` for the complete Gaia design document.

---

## License

This project was developed for academic purposes at the University of Jyväskylä.
TIES454 — Agent Technologies for Developers — April 2026.
