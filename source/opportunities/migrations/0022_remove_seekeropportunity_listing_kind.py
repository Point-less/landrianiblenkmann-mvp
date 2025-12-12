from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("opportunities", "0021_seekeropportunity_contract_expires_on_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="seekeropportunity",
            name="listing_kind",
        ),
    ]
