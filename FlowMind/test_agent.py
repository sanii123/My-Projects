import spade
import asyncio

class TestAgent(spade.agent.Agent):
    class HelloBehaviour(spade.behaviour.OneShotBehaviour):
        async def run(self):
            print("✅ SPADE is working! FlowMind ready to build.")
            await self.agent.stop()

    async def setup(self):
        print("🤖 Test Agent starting...")
        self.add_behaviour(self.HelloBehaviour())

async def main():
    agent = TestAgent("spade@localhost", "spade")
    await agent.start()
    await spade.wait_until_finished(agent)
    print("✅ Agent finished successfully!")

if __name__ == "__main__":
    spade.run(main())