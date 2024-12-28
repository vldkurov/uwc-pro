from uuid import uuid4

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from environs import Env

from locations.fields import OrderField
from locations.validators import validate_uk_phone_number, format_uk_phone_number

env = Env()
env.read_env()


class Division(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_by = models.ForeignKey(
        "accounts.CustomUser",
        related_name="created_groups",
        on_delete=models.SET_NULL,
        null=True,
    )
    updated_by = models.ForeignKey(
        "accounts.CustomUser",
        related_name="updated_groups",
        on_delete=models.SET_NULL,
        null=True,
    )
    title = models.CharField(
        _("Division Title"),
        max_length=100,
        unique=True,
    )
    slug = models.SlugField(max_length=255, unique=True)
    order = OrderField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]
        verbose_name = _("Division")
        verbose_name_plural = _("Divisions")
        permissions = [
            ("change_division_order", "Can change division order"),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse(
            "locations:division_edit",
            args=[
                self.slug,
            ],
        )

    def get_public_url(self):
        return reverse("locations", args=[self.slug])


class DisplayManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status=Branch.Status.DISPLAY)


class Branch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    class Status(models.TextChoices):
        HIDE = "HD", "Hide"
        DISPLAY = "DY", "Display"

    division = models.ForeignKey(
        "locations.Division",
        related_name="branches",
        on_delete=models.CASCADE,
        verbose_name=_("Division"),
    )
    title = models.CharField(_("Branch Name"), max_length=255, blank=True, null=True)
    slug = models.SlugField(max_length=255, unique=True)
    address = models.CharField(_("Address"), max_length=255, blank=True, null=True)
    formatted_address = models.CharField(
        _("Formatted Address"), max_length=255, blank=True, null=True
    )
    postcode = models.CharField(_("Postcode"), max_length=20, blank=True, null=True)
    parish_priest = models.ForeignKey(
        "locations.Person",
        related_name="parish_priest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Parish Priest"),
    )
    branch_chair = models.ForeignKey(
        "locations.Person",
        related_name="branch_chair",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Branch Chair"),
    )
    branch_secretary = models.ForeignKey(
        "locations.Person",
        related_name="branch_secretary",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Branch Secretary"),
    )
    other_details = models.TextField(
        _("Other Details"), max_length=500, blank=True, null=True
    )
    url = models.URLField(_("URL"), blank=True, null=True)
    status = models.CharField(max_length=2, choices=Status.choices, default=Status.HIDE)

    lat = models.FloatField(_("Latitude"), blank=True, null=True)
    lng = models.FloatField(_("Longitude"), blank=True, null=True)
    place_id = models.CharField(max_length=255, blank=True, null=True)

    objects = models.Manager()
    displayed = DisplayManager()

    class Meta:
        verbose_name = _("Branch")
        verbose_name_plural = _("Branches")
        permissions = [
            ("display", "Can display"),
            ("hide", "Can hide"),
        ]

    def save(self, *args, **kwargs):
        if self.address:
            self.address = self.format_address(self.address)
        super().save(*args, **kwargs)

    @staticmethod
    def format_address(address):
        words = address.split()
        return " ".join(word.capitalize() for word in words)

    def display(self):
        self.status = Branch.Status.DISPLAY
        self.save(update_fields=["status"])

    def hide(self):
        self.status = Branch.Status.HIDE
        self.save(update_fields=["status"])

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse(
            "locations:division_branch_update",
            kwargs={"division_slug": self.division.slug, "branch_slug": self.slug},
        )

    def get_public_url(self):
        return (
            reverse("locations", kwargs={"slug": self.division.slug})
            + f"#branch-{self.id}"
        )


class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    first_name = models.CharField(
        _("First Name"), max_length=100, blank=True, null=True
    )
    last_name = models.CharField(_("Last Name"), max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = _("Person")
        verbose_name_plural = _("People")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def get_absolute_url(self):
        return reverse(
            "locations:person_edit",
            kwargs={"pk": self.id},
        )

    def get_associated_branches(self):
        return Branch.displayed.filter(
            models.Q(parish_priest=self)
            | models.Q(branch_chair=self)
            | models.Q(branch_secretary=self)
        )


class Phone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    branch = models.ForeignKey(
        "locations.Branch",
        related_name="phones",
        on_delete=models.CASCADE,
        verbose_name=_("Branch"),
    )
    number = models.CharField(
        _("Phone Number"),
        max_length=20,
        blank=True,
        null=True,
        validators=[validate_uk_phone_number],
    )

    class Meta:
        verbose_name = _("Phone")
        verbose_name_plural = _("Phones")

    def save(self, *args, **kwargs):
        if self.number:
            self.number = format_uk_phone_number(self.number)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.number


class Email(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    branch = models.ForeignKey(
        "locations.Branch",
        related_name="emails",
        on_delete=models.CASCADE,
        verbose_name=_("Branch"),
    )
    email = models.EmailField(_("Email Address"), blank=True, null=True)

    class Meta:
        verbose_name = _("Email")
        verbose_name_plural = _("Emails")

    def __str__(self):
        return self.email
