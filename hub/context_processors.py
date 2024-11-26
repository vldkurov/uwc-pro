from django.conf import settings


def context_processor(request):
    return {
        "admin_path": settings.DJANGO_ADMIN_PATH,
    }
