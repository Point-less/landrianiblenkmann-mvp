from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0001_initial"),
        ("opportunities", "0005_alter_validationdocument_document_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="provideropportunity",
            name="tokkobroker_property",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="provider_opportunity",
                to="integrations.tokkobrokerproperty",
            ),
        ),
    ]

