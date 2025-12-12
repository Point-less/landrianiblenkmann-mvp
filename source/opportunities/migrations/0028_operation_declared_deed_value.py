from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("opportunities", "0027_operation_reserve_deadline"),
    ]

    operations = [
        migrations.AddField(
            model_name="operation",
            name="declared_deed_value",
            field=models.DecimalField(
                max_digits=14,
                decimal_places=2,
                null=True,
                blank=True,
                validators=[django.core.validators.MinValueValidator(0)],
                help_text="Declared deed value captured at reinforcement/closing.",
            ),
        ),
    ]
