# Generated by Django 5.1.3 on 2024-12-13 20:03

import django.db.models.deletion
import django.utils.timezone
import hub.fields
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="File",
            fields=[
                (
                    "title",
                    models.CharField(blank=True, default="", max_length=255, null=True),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("is_update_pending", models.BooleanField(default=False)),
                ("is_update_confirmed", models.BooleanField(default=False)),
                ("original_data", models.JSONField(blank=True, null=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("content", models.FileField(blank=True, null=True, upload_to="files")),
                (
                    "content_draft",
                    models.FileField(blank=True, null=True, upload_to="files"),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_related",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Image",
            fields=[
                (
                    "title",
                    models.CharField(blank=True, default="", max_length=255, null=True),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("is_update_pending", models.BooleanField(default=False)),
                ("is_update_confirmed", models.BooleanField(default=False)),
                ("original_data", models.JSONField(blank=True, null=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "content",
                    models.ImageField(blank=True, null=True, upload_to="images"),
                ),
                (
                    "content_draft",
                    models.ImageField(blank=True, null=True, upload_to="images"),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_related",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Page",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        max_length=255, unique=True, verbose_name="Page Title"
                    ),
                ),
                (
                    "title_en",
                    models.CharField(
                        max_length=255,
                        null=True,
                        unique=True,
                        verbose_name="Page Title",
                    ),
                ),
                (
                    "title_uk",
                    models.CharField(
                        max_length=255,
                        null=True,
                        unique=True,
                        verbose_name="Page Title",
                    ),
                ),
                ("slug", models.SlugField(max_length=255, unique=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "modified_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="pages",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Page",
                "verbose_name_plural": "Pages",
                "ordering": ["title"],
            },
        ),
        migrations.CreateModel(
            name="Section",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="Section Title",
                    ),
                ),
                (
                    "title_en",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="Section Title",
                    ),
                ),
                (
                    "title_uk",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="Section Title",
                    ),
                ),
                (
                    "title_draft",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="Section Title Draft",
                    ),
                ),
                (
                    "title_draft_en",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="Section Title Draft",
                    ),
                ),
                (
                    "title_draft_uk",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="Section Title Draft",
                    ),
                ),
                ("publish", models.DateTimeField(default=django.utils.timezone.now)),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("DF", "Draft"), ("PB", "Published")],
                        default="DF",
                        max_length=2,
                    ),
                ),
                ("order", hub.fields.OrderField(blank=True)),
                ("original_data", models.JSONField(blank=True, null=True)),
                ("is_update_pending_en", models.BooleanField(default=False)),
                ("is_update_pending_uk", models.BooleanField(default=False)),
                ("is_update_confirmed_en", models.BooleanField(default=False)),
                ("is_update_confirmed_uk", models.BooleanField(default=False)),
                (
                    "modified_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sections",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "page",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sections",
                        to="hub.page",
                    ),
                ),
            ],
            options={
                "verbose_name": "Section",
                "verbose_name_plural": "Sections",
                "ordering": ["order"],
                "permissions": [
                    ("request_update_en", "Can request update (English)"),
                    ("request_update_uk", "Can request update (Ukrainian)"),
                    ("confirm_update_en", "Can confirm update (English)"),
                    ("confirm_update_uk", "Can confirm update (Ukrainian)"),
                    ("reject_update_en", "Can reject update (English)"),
                    ("reject_update_uk", "Can reject update (Ukrainian)"),
                    ("publish_section", "Can publish"),
                    ("unpublish_section", "Can unpublish"),
                    ("change_section_order", "Can change section order"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Content",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("object_id", models.UUIDField()),
                ("order", hub.fields.OrderField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("HD", "Hide"), ("DY", "Display")],
                        default="HD",
                        max_length=2,
                    ),
                ),
                (
                    "content_type",
                    models.ForeignKey(
                        limit_choices_to={
                            "model__in": ("text", "file", "image", "video", "url")
                        },
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                    ),
                ),
                (
                    "section",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contents",
                        to="hub.section",
                    ),
                ),
            ],
            options={
                "verbose_name": "Content",
                "verbose_name_plural": "Contents",
                "ordering": ["order"],
                "permissions": [
                    ("request_update_en", "Can request update (English)"),
                    ("request_update_uk", "Can request update (Ukrainian)"),
                    ("confirm_update_en", "Can confirm update (English)"),
                    ("confirm_update_uk", "Can confirm update (Ukrainian)"),
                    ("reject_update_en", "Can reject update (English)"),
                    ("reject_update_uk", "Can reject update (Ukrainian)"),
                    ("request_update", "Can request update"),
                    ("confirm_update", "Can confirm update"),
                    ("reject_update", "Can reject update"),
                    ("display", "Can display"),
                    ("hide", "Can hide"),
                    ("change_content_order", "Can change content order"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Text",
            fields=[
                (
                    "title",
                    models.CharField(blank=True, default="", max_length=255, null=True),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("is_update_pending", models.BooleanField(default=False)),
                ("is_update_pending_en", models.BooleanField(default=False)),
                ("is_update_pending_uk", models.BooleanField(default=False)),
                ("is_update_confirmed", models.BooleanField(default=False)),
                ("is_update_confirmed_en", models.BooleanField(default=False)),
                ("is_update_confirmed_uk", models.BooleanField(default=False)),
                ("original_data", models.JSONField(blank=True, null=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "content",
                    models.TextField(blank=True, null=True, verbose_name="Content"),
                ),
                (
                    "content_en",
                    models.TextField(blank=True, null=True, verbose_name="Content"),
                ),
                (
                    "content_uk",
                    models.TextField(blank=True, null=True, verbose_name="Content"),
                ),
                (
                    "content_draft",
                    models.TextField(
                        blank=True, null=True, verbose_name="Content Draft"
                    ),
                ),
                (
                    "content_draft_en",
                    models.TextField(
                        blank=True, null=True, verbose_name="Content Draft"
                    ),
                ),
                (
                    "content_draft_uk",
                    models.TextField(
                        blank=True, null=True, verbose_name="Content Draft"
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_related",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="URL",
            fields=[
                (
                    "title",
                    models.CharField(blank=True, default="", max_length=255, null=True),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("is_update_pending", models.BooleanField(default=False)),
                ("is_update_confirmed", models.BooleanField(default=False)),
                ("original_data", models.JSONField(blank=True, null=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("content", models.URLField(blank=True, null=True)),
                ("content_draft", models.URLField(blank=True, null=True)),
                (
                    "modified_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_related",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Video",
            fields=[
                (
                    "title",
                    models.CharField(blank=True, default="", max_length=255, null=True),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("is_update_pending", models.BooleanField(default=False)),
                ("is_update_confirmed", models.BooleanField(default=False)),
                ("original_data", models.JSONField(blank=True, null=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("content", models.URLField(blank=True, null=True)),
                ("content_draft", models.URLField(blank=True, null=True)),
                (
                    "modified_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_related",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
