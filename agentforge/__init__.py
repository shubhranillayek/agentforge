"""AgentForge - build autonomous AI agents that plan, act, and remember.

Quick start::

    from agentforge import Agent, AgentConfig, tool, ToolRegistry

    @tool(description="Add two numbers.")
    def add(a: int, b: int) -> int:
        return a + b

    agent = Agent(name="mathie", llm=my_llm, tools=ToolRegistry(add))
    print(agent.run("What is 7 plus 5?"))
"""
from .core import Agent, AgentConfig
from .memory import ConversationBufferMemory, Message
from .tools import Tool, ToolRegistry, tool

__all__ = [
    "Agent",
    "AgentConfig",
    "ConversationBufferMemory",
    "Message",
    "Tool",
    "ToolRegistry",
    "tool",
]

__version__ = "0.1.0"
