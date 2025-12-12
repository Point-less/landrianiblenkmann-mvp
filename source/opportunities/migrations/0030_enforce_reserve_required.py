from django.db import migrations, models
import django.core.validators


def backfill_reserve(apps, schema_editor):
    Operation = apps.get_model("opportunities", "Operation")
    for op in Operation.objects.all():
        if op.reserve_amount is None:
            op.reserve_amount = 0
        if op.reserve_deadline is None:
            op.reserve_deadline = op.occurred_at.date() if op.occurred_at else None
        op.save(update_fields=["reserve_amount", "reserve_deadline"])


class Migration(migrations.Migration):

    dependencies = [
        ("opportunities", "0029_alter_operation_initial_offered_amount"),
    ]

    operations = [
        migrations.RunPython(backfill_reserve, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="operation",
            name="reserve_amount",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(0)],
                help_text="Remaining reserved funds after this step.",
            ),
        ),
        migrations.AlterField(
            model_name="operation",
            name="reserve_deadline",
            field=models.DateField(help_text="Deadline for the reserve amount."),
        ),
    ]
