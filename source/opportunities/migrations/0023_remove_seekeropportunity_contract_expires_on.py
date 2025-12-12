from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("opportunities", "0022_remove_seekeropportunity_listing_kind"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="seekeropportunity",
            name="contract_expires_on",
        ),
    ]
