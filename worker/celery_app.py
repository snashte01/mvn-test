from celery import Celery

celery = Celery(
    "zeroops",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["worker.tasks"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
