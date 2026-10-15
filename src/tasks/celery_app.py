from celery import Celery
from src.config.settings import settings

redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"

celery_app = Celery(
    "cinema_tasks",
    broker=redis_url,
    backend=redis_url,
    include=["src.tasks.accounts"],
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "delete-expired-tokens-every-hour": {
            "task": "src.tasks.accounts.delete_expired_tokens",
            "schedule": 3600.0,  # Run every hour
        },
    },
)
