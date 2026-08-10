# scenario_runner.py
# FlowMind – Scenario Runner
# Starts all agents and forces Scenario 1 and Scenario 2
# with controlled data so both are clearly demonstrated.
#
# Run with:  python scenario_runner.py

import asyncio
import json
import spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.message import Message

from config.settings import AGENTS, XMPP_PASSWORD
from agents.fault_detection_agent       import FaultDetectionAgent
from agents.diagnostic_agent            import DiagnosticAgent
from agents.people_flow_agent           import PeopleFlowAgent
from agents.dispatch_coordinator_agent  import DispatchCoordinatorAgent
from agents.reporting_agent             import ReportingAgent
from utils.dashboard_server             import run_dashboard_server
from utils.event_store                  import store


# ─────────────────────────────────────────────────────────────
# INJECTOR AGENT
# A lightweight agent whose only job is to send
# controlled messages directly to other agents,
# simulating FaultDetection and PeopleFlow output.
# ─────────────────────────────────────────────────────────────

class ScenarioInjectorAgent(Agent):

    def __init__(self, jid, password):
        super().__init__(jid, password)

    # ── Scenario 1: Routine Fault ─────────────────────────────
    # Low passenger count → no rush hour conflict
    # High vibration fault → triggers DISPATCH_TECHNICIAN goal
    # Expected BDI output: SCENARIO_1_ROUTINE_FAULT
    class InjectScenario1(OneShotBehaviour):

        async def run(self):
            eq_id = "ELV-01"

            print("\n" + "="*55)
            print("  🎬 INJECTING SCENARIO 1 — Routine Fault Dispatch")
            print(f"  Equipment : {eq_id}")
            print(f"  Condition : Off-peak hours, low passenger load")
            print(f"  Fault     : High vibration (bearing wear)")
            print(f"  Expected  : Scheduled or Emergency dispatch")
            print("="*55 + "\n")

            await asyncio.sleep(1)

            # Step 1: Send demand forecast (low passengers — NOT rush hour)
            forecast_msg = Message(to=AGENTS["dispatch"])
            forecast_msg.set_metadata("performative", "inform")
            forecast_msg.set_metadata("ontology",     "demand-forecast")
            forecast_msg.body = json.dumps({
                "msg_type":             "demand_forecast",
                "equipment_id":         eq_id,
                "predicted_passengers": 45,       # Low — off-peak
                "time_window":          "21:00-07:00",
                "risk_level":           "low",
            })
            await self.send(forecast_msg)
            print(f"[Injector] 📤 S1 — Demand forecast sent "
                  f"(45 pax, low risk)")

            await asyncio.sleep(1)

            # Step 2: Send fault alert
            fault_alert_msg = Message(to=AGENTS["dispatch"])
            fault_alert_msg.set_metadata("performative", "inform")
            fault_alert_msg.set_metadata("ontology",     "fault-alert")
            fault_alert_msg.body = json.dumps({
                "msg_type":     "fault_alert",
                "equipment_id": eq_id,
                "timestamp":    "2026-05-17 03:15:00",
                "severity":     "high",
            })
            await self.send(fault_alert_msg)
            print(f"[Injector] 📤 S1 — Fault alert sent "
                  f"(severity: HIGH)")

            await asyncio.sleep(1)

            # Step 3: Send fault signature to DiagnosticAgent
            fault_sig_msg = Message(to=AGENTS["diagnostic"])
            fault_sig_msg.set_metadata("performative", "inform")
            fault_sig_msg.set_metadata("ontology",     "fault-detection")
            fault_sig_msg.body = json.dumps({
                "msg_type":     "fault_signature",
                "equipment_id": eq_id,
                "timestamp":    "2026-05-17 03:15:00",
                "vibration":    9.8,    # High — above 7.0 threshold
                "temperature":  68.0,   # Normal
                "door_cycles":  410,    # Normal
                "severity":     "high",
            })
            await self.send(fault_sig_msg)
            print(f"[Injector] 📤 S1 — Fault signature sent "
                  f"→ DiagnosticAgent (vib=9.8)")

            print("\n[Injector] ✅ Scenario 1 injection complete. "
                  "Waiting for BDI reasoning...\n")

    # ── Scenario 2: Conflict — Rush Hour + Fault ──────────────
    # High passenger count → MINIMIZE_DISRUPTION goal added
    # Critical fault with very low TTF → RESTORE_SERVICE goal
    # Both goals active simultaneously → conflict detected
    # Expected BDI output: SCENARIO_2_CONFLICT_RESOLUTION
    class InjectScenario2(OneShotBehaviour):

        async def run(self):
            eq_id = "ELV-04"

            print("\n" + "="*55)
            print("  🎬 INJECTING SCENARIO 2 — Conflict Resolution")
            print(f"  Equipment : {eq_id}")
            print(f"  Condition : Morning rush hour, 340 passengers")
            print(f"  Fault     : Multiple faults, TTF < 2 hours")
            print(f"  Expected  : Conflict detected → safety wins")
            print("="*55 + "\n")

            await asyncio.sleep(1)

            # Step 1: Send demand forecast — HIGH passengers (rush hour)
            # This will trigger MINIMIZE_DISRUPTION + PASSENGER_SAFETY goals
            forecast_msg = Message(to=AGENTS["dispatch"])
            forecast_msg.set_metadata("performative", "inform")
            forecast_msg.set_metadata("ontology",     "demand-forecast")
            forecast_msg.body = json.dumps({
                "msg_type":             "demand_forecast",
                "equipment_id":         eq_id,
                "predicted_passengers": 340,      # Rush hour — triggers conflict
                "time_window":          "08:00-09:30",
                "risk_level":           "high",
            })
            await self.send(forecast_msg)
            print(f"[Injector] 📤 S2 — Demand forecast sent "
                  f"(340 pax, HIGH risk — rush hour)")

            await asyncio.sleep(1)

            # Step 2: Send fault alert during rush hour
            fault_alert_msg = Message(to=AGENTS["dispatch"])
            fault_alert_msg.set_metadata("performative", "inform")
            fault_alert_msg.set_metadata("ontology",     "fault-alert")
            fault_alert_msg.body = json.dumps({
                "msg_type":     "fault_alert",
                "equipment_id": eq_id,
                "timestamp":    "2026-05-17 08:42:00",
                "severity":     "high",
            })
            await self.send(fault_alert_msg)
            print(f"[Injector] 📤 S2 — Fault alert sent "
                  f"(severity: HIGH, during rush hour)")

            await asyncio.sleep(1)

            # Step 3: Send fault signature with multiple faults
            # Vibration + Temperature both above threshold → multiple_faults
            # DiagnosticAgent will compute TTF ~1.6h (critical)
            fault_sig_msg = Message(to=AGENTS["diagnostic"])
            fault_sig_msg.set_metadata("performative", "inform")
            fault_sig_msg.set_metadata("ontology",     "fault-detection")
            fault_sig_msg.body = json.dumps({
                "msg_type":     "fault_signature",
                "equipment_id": eq_id,
                "timestamp":    "2026-05-17 08:42:00",
                "vibration":    10.5,   # High — bearing failure
                "temperature":  88.0,   # High — motor overheating
                "door_cycles":  980,    # High — door wear
                "severity":     "high",
            })
            await self.send(fault_sig_msg)
            print(f"[Injector] 📤 S2 — Fault signature sent "
                  f"→ DiagnosticAgent "
                  f"(vib=10.5, temp=88.0, doors=980 — multiple faults)")

            print("\n[Injector] ✅ Scenario 2 injection complete. "
                  "Watching for conflict detection...\n")

    async def setup(self):
        print("[Injector] 🤖 Scenario Injector Agent started")
        # Only Scenario 1 starts automatically
        b1 = self.InjectScenario1()
        self.add_behaviour(b1)

# ─────────────────────────────────────────────────────────────
# MAIN — Start all agents then inject scenarios
# ─────────────────────────────────────────────────────────────

async def main():
    print("\n" + "="*55)
    print("  🚀 FLOWMIND — SCENARIO RUNNER")
    print("  BDI-Enhanced Multi-Agent System")
    print("  Two scenarios will run automatically:")
    print("  → Scenario 1: Routine Fault Dispatch")
    print("  → Scenario 2: Conflicting Goals (Rush Hour + Fault)")
    print("="*55 + "\n")

    # Start dashboard
    run_dashboard_server(port=5000)
    print("[Main] ✅ Dashboard running...")
    await asyncio.sleep(1)

    # Create all agents
    fault_agent      = FaultDetectionAgent(
        AGENTS["fault_detection"], XMPP_PASSWORD)
    diagnostic_agent = DiagnosticAgent(
        AGENTS["diagnostic"], XMPP_PASSWORD)
    people_flow_agent = PeopleFlowAgent(
        AGENTS["people_flow"], XMPP_PASSWORD)
    dispatch_agent   = DispatchCoordinatorAgent(
        AGENTS["dispatch"], XMPP_PASSWORD)
    reporting_agent  = ReportingAgent(
        AGENTS["reporting"], XMPP_PASSWORD)
    injector_agent   = ScenarioInjectorAgent(
        f"injector@{AGENTS['dispatch'].split('@')[1]}", XMPP_PASSWORD)

    # Start agents (reporting and dispatch first — they receive messages)
    print("[Main] Starting Reporting Agent...")
    await reporting_agent.start(auto_register=False)

    print("[Main] Starting Dispatch Coordinator Agent (BDI)...")
    await dispatch_agent.start(auto_register=False)

    print("[Main] Starting Diagnostic Agent...")
    await diagnostic_agent.start(auto_register=False)

    print("[Main] Starting People Flow Agent...")
    await people_flow_agent.start(auto_register=False)

    # Wait for agents to be ready
    await asyncio.sleep(3)

    print("[Main] Starting Scenario Injector...")
    await injector_agent.start(auto_register=True)

    # Wait for Scenario 1 to complete (12 seconds)
    print("\n[Main] ⏳ Running Scenario 1... (watch for BDI output)")
    await asyncio.sleep(12)

    # Manually trigger Scenario 2 after gap
    print("\n[Main] ⏳ Running Scenario 2... (watch for conflict detection)")
    b2 = injector_agent.InjectScenario2()
    injector_agent.add_behaviour(b2)
    await asyncio.sleep(15)

    print("\n" + "="*55)
    print("  ✅ Both scenarios complete.")
    print("  📊 Dashboard → http://localhost:5000/api/snapshot")
    print("  Press Ctrl+C to stop")
    print("="*55)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n[Main] ⛔ Shutdown requested...")
    finally:
        await fault_agent.stop()
        await diagnostic_agent.stop()
        await people_flow_agent.stop()
        await dispatch_agent.stop()
        await reporting_agent.stop()
        await injector_agent.stop()
        print("\n[Main] ⛔ FlowMind stopped.")


if __name__ == "__main__":
    spade.run(main())