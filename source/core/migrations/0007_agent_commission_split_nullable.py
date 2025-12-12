from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_remove_property_reference_code"),
    ]

    operations = [
        migrations.AlterField(
            model_name="agent",
            name="commission_split",
            field=models.DecimalField(
                blank=True,
                null=True,
                decimal_places=3,
                max_digits=4,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(1),
                ],
                help_text="Fraction (0-1) of commission allocated to this agent.",
            ),
        ),
        migrations.AlterField(
            model_name="agent",
            name="phone_number",
            field=models.CharField(blank=True, null=True, max_length=50),
        ),
    ]
