from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Response
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from workboard.database import get_session
from workboard.metrics import METRICS_PATH, metrics_response, record_metrics
from workboard.models import Task, TaskStatus
from workboard.schemas import TaskCreate, TaskRead, TaskUpdate

app = FastAPI(title="WorkBoard API", version="0.1.0")
app.middleware("http")(record_metrics)
DatabaseSession = Annotated[Session, Depends(get_session)]


def find_task(task_id: UUID, session: Session) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    return task


@app.get("/health/live")
def live():
    return {"status": "alive"}


@app.get(METRICS_PATH, include_in_schema=False)
def metrics():
    return metrics_response()


@app.get("/health/ready")
def ready(session: DatabaseSession):
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="DB に接続できません") from None
    return {"status": "ready"}


@app.get("/api/v1/tasks", response_model=list[TaskRead])
def list_tasks(session: DatabaseSession, status: TaskStatus | None = None):
    query = select(Task).order_by(Task.created_at.desc(), Task.id)
    if status is not None:
        query = query.where(Task.status == status)
    return session.scalars(query).all()


@app.post("/api/v1/tasks", response_model=TaskRead, status_code=201)
def create_task(body: TaskCreate, session: DatabaseSession):
    task = Task(**body.model_dump())
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@app.get("/api/v1/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: UUID, session: DatabaseSession):
    return find_task(task_id, session)


@app.patch("/api/v1/tasks/{task_id}", response_model=TaskRead)
def update_task(task_id: UUID, body: TaskUpdate, session: DatabaseSession):
    task = find_task(task_id, session)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    session.commit()
    session.refresh(task)
    return task


@app.delete("/api/v1/tasks/{task_id}", status_code=204)
def delete_task(task_id: UUID, session: DatabaseSession):
    session.delete(find_task(task_id, session))
    session.commit()
    return Response(status_code=204)
