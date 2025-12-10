from langchain.tools import tool
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig

class AskUserInput(BaseModel):
    """Input for ask_user"""
    question: str = Field(description="The question to ask the user")
    justification: str = Field(
        description="Additional context explaining why the question is being asked.")

@tool(args_schema=AskUserInput)
def ask_user(question: str, justification: str, config: RunnableConfig):
    """
    Ask a question to the user
    """

    # 1. Access the configuration dictionary
    configuration = config.get("configurable", {})

    # 2. Retrieve the lock (handle case where it's missing)
    lock = configuration.get("thread_lock")
    if not lock:
        raise ValueError("Thread lock was not passed in config!")

    with lock:
        print(f"question: {question} ({justification})")
        return input("> ")
