from copy import deepcopy

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models, transaction
from django.db.models import Max


class FSMLoggableMixin(models.Model):
    """Attach django-fsm-log entries to a model instance."""

    state_logs = GenericRelation(
        "django_fsm_log.StateLog",
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="%(app_label)s_%(class)s_state_logs",
    )
    state_transitions = GenericRelation(
        "utils.FSMStateTransition",
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="%(app_label)s_%(class)s_state_transitions",
    )

    class Meta:
        abstract = True

    def latest_state_log(self):
        return self.state_logs.order_by("-timestamp").first()

    def state_history(self):
        return self.state_logs.order_by("-timestamp")



class TimeStampedMixin(models.Model):
    """Abstract mixin adding created/updated auditing fields."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TimeStampedModel(TimeStampedMixin):
    class Meta(TimeStampedMixin.Meta):
        abstract = True


class ImmutableRevisionMixin(models.Model):
    """Abstract helper enforcing immutable, versioned revisions."""

    VERSION_FIELD = 'version'
    ACTIVE_FIELD = 'is_active'
    REVISION_SCOPE = tuple()
    IMMUTABLE_ALLOW_UPDATES = frozenset({'is_active', 'updated_at'})
    IMMUTABLE_EXCLUDE_FIELDS = tuple()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk:
            update_fields = kwargs.get('update_fields')
            if update_fields is None:
                model_label = self.__class__.__name__
                raise ValueError(f"{model_label} instances are immutable; use create_revision instead of saving in place.")
            allowed = set(self.IMMUTABLE_ALLOW_UPDATES)
            if not set(update_fields).issubset(allowed):
                model_label = self.__class__.__name__
                raise ValueError(f"{model_label} instances are immutable; use create_revision instead of saving in place.")
        super().save(*args, **kwargs)

    @classmethod
    def editable_field_names(cls):
        excluded = {
            cls._meta.pk.name,
            cls.VERSION_FIELD,
            cls.ACTIVE_FIELD,
            'created_at',
            'updated_at',
        }
        excluded.update(cls.REVISION_SCOPE)
        excluded.update(getattr(cls, 'IMMUTABLE_EXCLUDE_FIELDS', ()))
        field_names = []
        for field in cls._meta.get_fields():
            if not isinstance(field, models.Field) or field.auto_created:
                continue
            if field.name in excluded:
                continue
            field_names.append(field.name)
        return field_names

    @classmethod
    def prepare_revision_payload(cls, instance):
        payload = {}
        for name in cls.editable_field_names():
            value = getattr(instance, name)
            if isinstance(value, (list, dict)):
                value = deepcopy(value)
            payload[name] = value
        return payload

    @classmethod
    def create_revision(cls, instance, **changes):
        if not cls.REVISION_SCOPE:
            raise ValueError('REVISION_SCOPE must be defined for immutable revision models.')
        base_payload = cls.prepare_revision_payload(instance)
        base_payload.update(changes)
        scope_filter = {field: getattr(instance, field) for field in cls.REVISION_SCOPE}
        with transaction.atomic():
            setattr(instance, cls.ACTIVE_FIELD, False)
            instance.save(update_fields=[cls.ACTIVE_FIELD, 'updated_at'])
            max_version = (
                cls.objects.filter(**scope_filter)
                .aggregate(max_v=Max(cls.VERSION_FIELD))
                .get('max_v')
                or 0
            )
            create_kwargs = {**scope_filter, **base_payload}
            create_kwargs[cls.VERSION_FIELD] = max_version + 1
            create_kwargs[cls.ACTIVE_FIELD] = True
            new_instance = cls.objects.create(**create_kwargs)
        return new_instance

    def clone(self, **overrides):
        return type(self).create_revision(self, **overrides)
