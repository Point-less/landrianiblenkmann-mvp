from django.http import JsonResponse

from .tasks import log_message


def health_check(request):
    return JsonResponse({'status': 'ok'})


def trigger_log(request):
    message = request.GET.get('message', 'Health check ping received')
    task = log_message.delay(message)
    return JsonResponse({'status': 'queued', 'task_id': task.id})
