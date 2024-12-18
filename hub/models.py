import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from .fields import OrderField

COMMON_PERMISSIONS = [
    ("request_update_en", "Can request update (English)"),
    ("request_update_uk", "Can request update (Ukrainian)"),
    ("confirm_update_en", "Can confirm update (English)"),
    ("confirm_update_uk", "Can confirm update (Ukrainian)"),
    ("reject_update_en", "Can reject update (English)"),
    ("reject_update_uk", "Can reject update (Ukrainian)"),
]


class PublishedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status=Section.Status.PUBLISHED)


class Page(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    modified_by = models.ForeignKey(
        "accounts.CustomUser",
        related_name="pages",
        on_delete=models.SET_NULL,
        null=True,
    )
    title = models.CharField(
        _("Page Title"), max_length=255, unique=True, blank=False, null=False
    )
    slug = models.SlugField(max_length=255, unique=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")

    def save(self, *args, **kwargs):
        existing_title = Page.objects.filter(pk=self.pk).values("title").first()
        if (
            not self.pk
            or not self.slug
            or (
                self.pk
                and existing_title
                and self.title != existing_title.get("title", "")
            )
        ):
            self.slug = slugify(self.title)
        super(Page, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse(
            "page_edit",
            args=[
                self.slug,
            ],
        )

    def get_public_url(self):
        return reverse("page", args=[self.slug])


class Section(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Status(models.TextChoices):
        DRAFT = "DF", "Draft"
        PUBLISHED = "PB", "Published"

    modified_by = models.ForeignKey(
        "accounts.CustomUser",
        related_name="sections",
        on_delete=models.SET_NULL,
        null=True,
    )
    page = models.ForeignKey(Page, related_name="sections", on_delete=models.CASCADE)
    title = models.CharField(_("Section Title"), max_length=255, blank=True, null=True)
    title_draft = models.CharField(
        _("Section Title Draft"), max_length=255, blank=True, null=True
    )
    publish = models.DateTimeField(default=timezone.now)
    created = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=2, choices=Status, default=Status.DRAFT)
    objects = models.Manager()
    published = PublishedManager()
    order = OrderField(blank=True, for_fields=["page"])
    original_data = models.JSONField(null=True, blank=True)

    is_update_pending_en = models.BooleanField(default=False)
    is_update_pending_uk = models.BooleanField(default=False)
    is_update_confirmed_en = models.BooleanField(default=False)
    is_update_confirmed_uk = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("Section")
        verbose_name_plural = _("Sections")
        ordering = ["order"]

        permissions = COMMON_PERMISSIONS + [
            ("publish_section", "Can publish"),
            ("unpublish_section", "Can unpublish"),
            ("change_section_order", "Can change section order"),
        ]

    def __str__(self):
        return f"{self.order}. {self.title}"

    def get_absolute_url(self):
        return reverse(
            "page_section_update",
            args=[
                self.page.slug,
            ],
        )

    def get_public_url(self):
        return reverse("page", args=[self.page.slug])


class DisplayManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status=Content.Status.DISPLAY)


class Content(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Status(models.TextChoices):
        HIDE = "HD", "Hide"
        DISPLAY = "DY", "Display"

    section = models.ForeignKey(
        Section, related_name="contents", on_delete=models.CASCADE
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={"model__in": ("text", "file", "image", "video", "url")},
    )
    object_id = models.UUIDField()
    item = GenericForeignKey("content_type", "object_id")
    order = OrderField(blank=True, for_fields=["section"])
    status = models.CharField(max_length=2, choices=Status.choices, default=Status.HIDE)

    objects = models.Manager()
    displayed = DisplayManager()

    class Meta:
        verbose_name = _("Content")
        verbose_name_plural = _("Contents")
        ordering = ["order"]
        permissions = COMMON_PERMISSIONS + [
            ("request_update", "Can request update"),
            ("confirm_update", "Can confirm update"),
            ("reject_update", "Can reject update"),
            ("display", "Can display"),
            ("hide", "Can hide"),
            ("change_content_order", "Can change content order"),
        ]

    def display(self):
        self.status = Content.Status.DISPLAY
        self.save(update_fields=["status"])

    def hide(self):
        self.status = Content.Status.HIDE
        self.save(update_fields=["status"])


class ItemBase(models.Model):
    modified_by = models.ForeignKey(
        "accounts.CustomUser",
        related_name="%(class)s_related",
        on_delete=models.SET_NULL,
        null=True,
    )
    title = models.CharField(max_length=255, blank=True, null=True, default="")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        try:
            content_link = Content.objects.get(
                object_id=self.id,
                content_type=ContentType.objects.get_for_model(self),
            )
            return reverse(
                "section_content_update",
                kwargs={
                    "section_id": content_link.section.id,
                    "model_name": self.__class__.__name__.lower(),
                    "id": self.id,
                },
            )
        except ObjectDoesNotExist:
            return "#"

    def get_public_url(self):
        """
        Forms the public URL for content with an anchor to scroll to it.
        """
        try:
            content_link = Content.objects.get(
                object_id=self.id,
                content_type=ContentType.objects.get_for_model(self),
            )
            page_slug = content_link.section.page.slug
            anchor = f"#content-{self.id}"
            return reverse("page", kwargs={"slug": page_slug}) + anchor
        except ObjectDoesNotExist:
            return "#"


class Updatable(models.Model):
    is_update_pending = models.BooleanField(default=False)
    is_update_confirmed = models.BooleanField(default=False)
    original_data = models.JSONField(null=True, blank=True)

    class Meta:
        abstract = True


class Text(ItemBase, Updatable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.TextField(_("Content"), blank=True, null=True)
    content_draft = models.TextField(_("Content Draft"), blank=True, null=True)


class File(ItemBase, Updatable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.FileField(upload_to="files", blank=True, null=True)
    content_draft = models.FileField(upload_to="files", blank=True, null=True)


class Image(ItemBase, Updatable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ImageField(upload_to="images", blank=True, null=True)
    content_draft = models.ImageField(upload_to="images", blank=True, null=True)


class Video(ItemBase, Updatable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.URLField(blank=True, null=True)
    content_draft = models.URLField(blank=True, null=True)


class URL(ItemBase, Updatable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.URLField(blank=True, null=True)
    content_draft = models.URLField(blank=True, null=True)
