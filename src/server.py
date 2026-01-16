import argparse
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

from executor import Executor


def main():
    parser = argparse.ArgumentParser(description="Run the A2A agent.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind the server")
    parser.add_argument("--port", type=int, default=9009, help="Port to bind the server")
    parser.add_argument("--card-url", type=str, help="URL to advertise in the agent card")
    args = parser.parse_args()

    # Fill in your agent card
    # See: https://a2a-protocol.org/latest/tutorials/python/3-agent-skills-and-card/
    
    # A single skill is enough for A2A conformance tests and for the DMC evaluator
    # to discover what this agent does.
    skill = AgentSkill(
        id="dmc_control",
        name="DMC Control (Baseline)",
        description=(
            "Responds to DeepMind Control Suite evaluator messages (dmc_init/dmc_step) "
            "with JSON actions matching the provided action_spec."
        ),
        tags=["dm_control", "reinforcement-learning", "baseline"],
        examples=[
            "{\"kind\": \"dmc_step\", \"action_spec\": {\"shape\": [2], \"minimum\": [-1, -1], \"maximum\": [1, 1]}}",
        ],
    )

    agent_card = AgentCard(
        name="DMC Purple Agent (Baseline)",
        description="A minimal baseline agent that outputs random continuous actions for DMC tasks.",
        url=args.card_url or f"http://{args.host}:{args.port}/",
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill]
    )

    request_handler = DefaultRequestHandler(
        agent_executor=Executor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )
    uvicorn.run(server.build(), host=args.host, port=args.port)


if __name__ == '__main__':
    main()
