from typing import List, Optional, Annotated

import typer
from rich.console import Console
from rich.table import Table

from playground.tasks import services

app = typer.Typer()
state = {"db_path": ""}


@app.callback()
def main(db_path: str = typer.Option("tasks.sqlite", "--db-path")):
    state["db_path"] = db_path
    services.init_db(db_path)


@app.command("load-tasks")
def load_tasks(file: str = typer.Option(..., "--file")):
    """
    Load tasks from a JSON file.
    """
    count = services.load_tasks(state["db_path"], file)
    print(f"Loaded {count} tasks from {file}")


@app.command("start-session")
def start_session(
    url: str = typer.Option(..., "--url"),
    task_ids: Annotated[List[int], typer.Argument()] = None,
):
    """
    Start a new session with the given tasks.
    """
    try:
        session_id = services.start_session(state["db_path"], url, task_ids)
        print(f"Started new session with id {session_id}")
    except ValueError as e:
        print(e)
        raise typer.Exit(code=1)


@app.command("list-sessions")
def list_sessions(status: Optional[str] = typer.Argument(None)):
    """
    List sessions, optionally filtering by status.
    """
    sessions = services.list_sessions(state["db_path"], status)
    table = Table("ID", "URL", "Status", "Tasks", "Completed At")
    for s in sessions:
        task_ids = ", ".join([str(task.id) for task in s.tasks])
        table.add_row(str(s.id), s.url, s.status, task_ids, str(s.completedAt) if s.completedAt else "")

    console = Console()
    console.print(table)


@app.command("review-session")
def review_session(session_id: int, status: str):
    """
    Review a session, marking it as passed or failed.
    """
    try:
        services.review_session(state["db_path"], session_id, status)
        print(f"Session {session_id} marked as {status}")
    except ValueError as e:
        print(e)
        raise typer.Exit(code=1)


@app.command("list-tasks")
def list_tasks(status: Optional[str] = typer.Argument(None)):
    """
    List tasks, optionally filtering by status (passed/failed).
    """
    tasks = services.list_tasks(state["db_path"], status)
    table = Table("ID", "Category", "Description", "Passed")
    for task in tasks:
        table.add_row(str(task.id), task.category, task.description, str(task.passes))

    console = Console()
    console.print(table)


@app.command("view-tasks")
def view_tasks(task_ids: Annotated[List[int], typer.Argument()] = None):
    """
    View details of one or more tasks.
    """
    tasks = services.view_tasks(state["db_path"], task_ids)
    if not tasks:
        print("No tasks found with the given IDs.")
        return

    for task in tasks:
        if task:
            print(f"\n--- Task ID: {task.id} ---")
            print(f"Category: {task.category}")
            print(f"Description: {task.description}")
            print("Steps:")
            for step in task.steps:
                print(f"  - {step}")
            print(f"Passed: {task.passes}")
        else:
            # This part of the logic might not be reached if services.view_tasks only returns found tasks
            print(f"Task with a provided ID was not found.")


if __name__ == "__main__":
    app()
