from typing import List, Optional

from langchain.tools import tool
from pydantic import BaseModel, Field

from playground.tasks import services


class ListTasksInput(BaseModel):
    """Input for list_tasks tool."""
    status: Optional[str] = Field(..., description="Filter tasks by status")
    db_path: str = Field("tasks.sqlite", description="Path to the SQLite database file.")


@tool(args_schema=ListTasksInput)
def list_tasks(status: Optional[str] = None, db_path: str = "tasks.sqlite") -> List[dict]:
    """
    List tasks, optionally filtering by status.
    """
    services.init_db(db_path)
    tasks = services.list_tasks(db_path, status)
    return [task.model_dump() for task in tasks]


class ViewTasksInput(BaseModel):
    """Input for view_tasks tool."""
    task_ids: List[int] = Field(..., description="A list of task IDs to view.")
    db_path: str = Field("tasks.sqlite", description="Path to the SQLite database file.")


@tool(args_schema=ViewTasksInput)
def view_tasks(task_ids: List[int], db_path: str = "tasks.sqlite") -> List[dict]:
    """
    View details of one or more tasks.
    """
    services.init_db(db_path)
    tasks = services.view_tasks(db_path, task_ids)
    return [task.model_dump() for task in tasks]
