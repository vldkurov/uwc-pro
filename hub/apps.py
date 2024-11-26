from django.apps import AppConfig


class AdminPagesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub"

    def ready(self):
        import hub.signals  # noqa: F401 (used for side effects)
