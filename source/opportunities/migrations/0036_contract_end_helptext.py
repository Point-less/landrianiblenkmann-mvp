from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("opportunities", "0035_provideropportunity_prefill_val_values"),
    ]

    operations = [
        migrations.AlterField(
            model_name="provideropportunity",
            name="contract_expires_on",
            field=models.DateField(blank=True, help_text="Contract end date.", null=True),
        ),
    ]
