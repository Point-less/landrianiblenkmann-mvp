from celery import shared_task


@shared_task
def add(x, y):
    return x + y


@shared_task
def log_message(message: str = "Hello from Celery"):
    print(f"Celery says: {message}")
