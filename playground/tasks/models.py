import datetime
from typing import List, Optional

from sqlmodel import Field, SQLModel, JSON, Column, Relationship


class SessionTaskLink(SQLModel, table=True):
    session_id: Optional[int] = Field(
        default=None, foreign_key="session.id", primary_key=True
    )
    task_id: Optional[int] = Field(
        default=None, foreign_key="task.id", primary_key=True
    )


class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    category: str
    description: str
    steps: List[str] = Field(sa_column=Column(JSON))
    passes: bool = False
    sessions: List["Session"] = Relationship(back_populates="tasks", link_model=SessionTaskLink)


class Session(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str
    status: str
    createdAt: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    completedAt: Optional[datetime.datetime] = None
    tasks: List["Task"] = Relationship(back_populates="sessions", link_model=SessionTaskLink)
