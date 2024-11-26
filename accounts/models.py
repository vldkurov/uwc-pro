import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Role(models.TextChoices):
        OWNER = "OWR", "Owner"
        ADMIN = "ADM", "Admin"
        EDITOR = "EDT", "Editor"
        VIEWER = "VWR", "Viewer"

    role = models.CharField(max_length=3, choices=Role.choices, default=Role.VIEWER)
