import datetime
import json
from typing import List, Optional

from sqlmodel import create_engine, Session as SQLModelSession, select

from playground.tasks.models import Task, Session, SQLModel


def init_db(db_path: str):
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)


def load_tasks(db_path: str, file: str) -> int:
    """
    Load tasks from a JSON file.
    """
    engine = create_engine(f"sqlite:///{db_path}")
    with SQLModelSession(engine) as session:
        with open(file, "r") as f:
            tasks_data = json.load(f)
            for task_data in tasks_data:
                existing_task = session.exec(select(Task).where(Task.description == task_data["description"])).first()
                if existing_task:
                    for key, value in task_data.items():
                        setattr(existing_task, key, value)
                    session.add(existing_task)
                else:
                    task = Task(**task_data)
                    session.add(task)
            session.commit()
    return len(tasks_data)


def start_session(db_path: str, url: str, task_ids: Optional[List[int]] = None) -> int:
    """
    Start a new session with the given tasks.
    """
    engine = create_engine(f"sqlite:///{db_path}")
    with SQLModelSession(engine) as session:
        tasks = []
        if task_ids:
            for task_id in task_ids:
                task = session.get(Task, task_id)
                if not task:
                    raise ValueError(f"Task with id {task_id} not found")
                tasks.append(task)

        new_session = Session(url=url, status="started", tasks=tasks)
        session.add(new_session)
        session.commit()
        session.refresh(new_session)
        return new_session.id


def list_sessions(db_path: str, status: Optional[str] = None) -> List[Session]:
    """
    List sessions, optionally filtering by status.
    """
    engine = create_engine(f"sqlite:///{db_path}")
    with SQLModelSession(engine) as session:
        statement = select(Session)
        if status:
            statement = statement.where(Session.status == status)
        sessions = session.exec(statement).all()
        return sessions


def review_session(db_path: str, session_id: int, status: str) -> Session:
    """
    Review a session, marking it as passed or failed.
    """
    engine = create_engine(f"sqlite:///{db_path}")
    with SQLModelSession(engine) as session:
        session_to_review = session.get(Session, session_id)
        if not session_to_review:
            raise ValueError(f"Session with id {session_id} not found")

        session_to_review.status = status
        session_to_review.completedAt = datetime.datetime.utcnow()
        if status == "passed":
            for task in session_to_review.tasks:
                task.passes = True
                session.add(task)

        session.add(session_to_review)
        session.commit()
        session.refresh(session_to_review)
        return session_to_review


def list_tasks(db_path: str, status: Optional[str] = None) -> List[Task]:
    """
    List tasks, optionally filtering by status (passed/failed).
    """
    engine = create_engine(f"sqlite:///{db_path}")
    with SQLModelSession(engine) as session:
        statement = select(Task)
        if status == "passed":
            statement = statement.where(Task.passes == True)
        elif status == "failed":
            statement = statement.where(Task.passes == False)
        tasks = session.exec(statement).all()
        return tasks


def view_tasks(db_path: str, task_ids: List[int]) -> List[Task]:
    """
    View details of one or more tasks.
    """
    engine = create_engine(f"sqlite:///{db_path}")
    with SQLModelSession(engine) as session:
        tasks = []
        for task_id in task_ids:
            task = session.get(Task, task_id)
            if task:
                tasks.append(task)
        return tasks
