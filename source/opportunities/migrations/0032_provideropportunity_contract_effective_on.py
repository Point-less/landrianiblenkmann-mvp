from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("opportunities", "0031_contract_expires_on_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="provideropportunity",
            name="contract_effective_on",
            field=models.DateField(
                blank=True,
                null=True,
                help_text="Contract effective/start date.",
            ),
        ),
    ]
