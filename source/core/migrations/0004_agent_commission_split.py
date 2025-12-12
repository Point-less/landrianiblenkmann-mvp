from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_contact_full_address_contact_full_name_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="agent",
            name="commission_split",
            field=models.DecimalField(
                decimal_places=3,
                default=0,
                max_digits=4,
                validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)],
                help_text="Fraction (0-1) of commission allocated to this agent.",
            ),
        ),
    ]
