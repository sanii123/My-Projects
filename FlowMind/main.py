# main.py
# FlowMind – Multi-Agent System Entry Point

import asyncio
import spade

from config.settings import AGENTS, XMPP_PASSWORD
from agents.fault_detection_agent      import FaultDetectionAgent
from agents.diagnostic_agent           import DiagnosticAgent
from agents.people_flow_agent          import PeopleFlowAgent
from agents.dispatch_coordinator_agent import DispatchCoordinatorAgent
from agents.reporting_agent            import ReportingAgent
from utils.dashboard_server            import run_dashboard_server


async def main():
    print("\n" + "="*55)
    print("  🚀 FLOWMIND MULTI-AGENT SYSTEM STARTING...")
    print("  Smart Elevator & Escalator Management")
    print("  University of Jyvaskyla — TIES454")
    print("  Group: Neural Nexus")
    print("="*55 + "\n")

    # Step 1: Start Flask dashboard server first
    run_dashboard_server(port=5000)
    print("[Main] ✅ Dashboard server running...")
    await asyncio.sleep(1)

    # Step 2: Create all agents
    fault_agent    = FaultDetectionAgent(
        AGENTS["fault_detection"], XMPP_PASSWORD
    )
    diagnostic_agent = DiagnosticAgent(
        AGENTS["diagnostic"], XMPP_PASSWORD
    )
    people_flow_agent = PeopleFlowAgent(
        AGENTS["people_flow"], XMPP_PASSWORD
    )
    dispatch_agent = DispatchCoordinatorAgent(
        AGENTS["dispatch"], XMPP_PASSWORD
    )
    reporting_agent = ReportingAgent(
        AGENTS["reporting"], XMPP_PASSWORD
    )

    # Step 3: Start all agents
    print("[Main] Starting Reporting Agent...")
    await reporting_agent.start(auto_register=False)

    print("[Main] Starting Dispatch Coordinator Agent...")
    await dispatch_agent.start(auto_register=False)

    print("[Main] Starting Diagnostic Agent...")
    await diagnostic_agent.start(auto_register=False)

    print("[Main] Starting People Flow Predictor Agent...")
    await people_flow_agent.start(auto_register=False)

    # Wait so other agents are ready
    await asyncio.sleep(3)

    print("[Main] Starting Fault Detection Agent...")
    await fault_agent.start(auto_register=False)

    print("\n" + "="*55)
    print("  ✅ ALL AGENTS RUNNING — System is LIVE")
    print("  📊 Dashboard → http://localhost:5000/api/snapshot")
    print("  🌐 Open dashboard.html in your browser")
    print("  Press Ctrl+C to stop")
    print("="*55 + "\n")

    # Step 4: Keep running
    try:
        while True:
            await asyncio.sleep(1)
            if not any([
                fault_agent.is_alive(),
                diagnostic_agent.is_alive(),
                people_flow_agent.is_alive(),
                dispatch_agent.is_alive(),
                reporting_agent.is_alive(),
            ]):
                print("[Main] All agents stopped.")
                break

    except KeyboardInterrupt:
        print("\n[Main] ⛔ Shutdown requested...")

    finally:
        print("[Main] Stopping all agents...")
        await fault_agent.stop()
        await diagnostic_agent.stop()
        await people_flow_agent.stop()
        await dispatch_agent.stop()
        await reporting_agent.stop()
        print("\n[Main] ⛔ FlowMind stopped.")


if __name__ == "__main__":
    spade.run(main())