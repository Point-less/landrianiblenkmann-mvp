from django.db import migrations, models
import django.core.validators


def backfill_initial_and_currency(apps, schema_editor):
    Operation = apps.get_model("opportunities", "Operation")
    for op in Operation.objects.all():
        if getattr(op, "initial_offered_amount", None) is None:
            op.initial_offered_amount = op.offered_amount or 0
        if op.currency_id is None:
            # Try seeker intention currency fallback, else provider intention valuation currency (if exists), else leave as None.
            seeker_intent = op.seeker_opportunity.source_intention
            currency_id = getattr(seeker_intent, "currency_id", None)
            if currency_id:
                op.currency_id = currency_id
        op.save(update_fields=["initial_offered_amount", "currency_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("opportunities", "0025_provideropportunity_contract_expires_on"),
    ]

    operations = [
        migrations.AddField(
            model_name="operation",
            name="initial_offered_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(0)],
                help_text="Initial offered amount at operation creation.",
            ),
        ),
        migrations.RunPython(backfill_initial_and_currency, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="operation",
            name="currency",
            field=models.ForeignKey(on_delete=models.PROTECT, related_name="operations", to="core.currency"),
        ),
        migrations.AlterField(
            model_name="operation",
            name="offered_amount",
            field=models.DecimalField(
                blank=True,
                null=True,
                decimal_places=2,
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(0)],
                help_text="Current offered amount (set when reinforced).",
            ),
        ),
        migrations.AlterField(
            model_name="operation",
            name="reinforcement_amount",
            field=models.DecimalField(
                blank=True,
                null=True,
                decimal_places=2,
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(0)],
                help_text="Additional funds available when reinforced.",
            ),
        ),
    ]
