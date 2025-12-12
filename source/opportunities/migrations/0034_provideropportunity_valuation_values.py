from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("opportunities", "0032_provideropportunity_contract_effective_on"),
        ("intentions", "0011_salevaluation_test_close_values"),
    ]

    operations = [
        migrations.AddField(
            model_name="provideropportunity",
            name="valuation_test_value",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AddField(
            model_name="provideropportunity",
            name="valuation_close_value",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12, validators=[django.core.validators.MinValueValidator(0)]),
        ),
    ]
