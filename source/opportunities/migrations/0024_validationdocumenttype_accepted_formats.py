from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("opportunities", "0023_remove_seekeropportunity_contract_expires_on"),
    ]

    operations = [
        migrations.AddField(
            model_name="validationdocumenttype",
            name="accepted_formats",
            field=models.JSONField(
                default=list,
                blank=True,
                help_text="Allowed file extensions (e.g., ['.pdf', '.jpg']); leave empty to use system defaults.",
            ),
        ),
    ]
