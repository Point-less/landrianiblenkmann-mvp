from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("intentions", "0010_salevaluation_valuation_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="salevaluation",
            name="test_value",
            field=models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0)], default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="salevaluation",
            name="close_value",
            field=models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0)], default=0),
            preserve_default=False,
        ),
    ]
