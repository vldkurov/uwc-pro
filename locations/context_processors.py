from .models import Division


def divisions_context(request):
    first_division = Division.objects.first()

    return {
        "division": first_division,
        "has_divisions": first_division is not None,  # Флаг наличия объектов Division
    }
