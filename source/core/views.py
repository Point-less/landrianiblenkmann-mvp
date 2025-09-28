from django.http import JsonResponse

from .tasks import log_message


async def health_check(request):
    return JsonResponse({'status': 'ok'})


async def trigger_log(request):
    message = request.GET.get('message', 'Health check ping received')
    task = log_message.delay(message)
    return JsonResponse({'status': 'queued', 'task_id': task.id})
