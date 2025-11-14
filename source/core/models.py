from django.db import models

from utils.mixins import TimeStampedMixin


class Currency(TimeStampedMixin):
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10, blank=True)

    class Meta:
        ordering = ("code",)
        verbose_name = "currency"
        verbose_name_plural = "currencies"

    def __str__(self) -> str:
        return self.code


class Contact(TimeStampedMixin):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("last_name", "first_name")
        verbose_name = "contact"
        verbose_name_plural = "contacts"
        db_table = "opportunities_contact"

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Agent(TimeStampedMixin):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    contacts = models.ManyToManyField(
        "core.Contact",
        through="core.ContactAgentRelationship",
        related_name="agents",
        blank=True,
    )

    class Meta:
        ordering = ("last_name", "first_name")
        verbose_name = "agent"
        verbose_name_plural = "agents"
        db_table = "opportunities_agent"

    def __str__(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.email or "Agent"


class Property(TimeStampedMixin):
    name = models.CharField(max_length=255)
    reference_code = models.CharField(max_length=50, blank=True, unique=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "property"
        verbose_name_plural = "properties"
        db_table = "opportunities_property"

    def __str__(self) -> str:
        return self.name


class ContactAgentRelationship(TimeStampedMixin):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        FORMER = "former", "Former"

    agent = models.ForeignKey(
        'core.Agent',
        on_delete=models.CASCADE,
        related_name='contact_links',
    )
    contact = models.ForeignKey(
        'core.Contact',
        on_delete=models.CASCADE,
        related_name='agent_links',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    relationship_notes = models.TextField(blank=True)
    started_on = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        unique_together = (("agent", "contact"),)
        verbose_name = "contact agent relationship"
        verbose_name_plural = "contact agent relationships"

    def __str__(self) -> str:
        return f"{self.contact} <> {self.agent}"


class TokkobrokerProperty(TimeStampedMixin):
    """Minimal registry entry for Tokkobroker-sourced properties."""

    tokko_id = models.PositiveIntegerField(unique=True)
    ref_code = models.CharField(max_length=64)
    address = models.CharField(max_length=255, blank=True)
    tokko_created_at = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Tokkobroker property"
        verbose_name_plural = "Tokkobroker properties"

    def __str__(self) -> str:
        return f"{self.ref_code} ({self.tokko_id})"


__all__ = [
    "Agent",
    "Contact",
    "ContactAgentRelationship",
    "Currency",
    "Property",
    "TokkobrokerProperty",
]
