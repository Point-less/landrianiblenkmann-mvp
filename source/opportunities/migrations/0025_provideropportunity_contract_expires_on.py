from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("opportunities", "0024_validationdocumenttype_accepted_formats"),
    ]

    operations = [
        migrations.AddField(
            model_name="provideropportunity",
            name="contract_expires_on",
            field=models.DateField(blank=True, null=True),
        ),
    ]
