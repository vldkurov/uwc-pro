from .models import Division


def divisions_context(request):
    objects = Division.objects.first()
    return {"division": objects}
