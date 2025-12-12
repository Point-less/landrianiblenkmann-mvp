from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def ensure_no_null_tokkobroker(apps, schema_editor):
    ProviderOpportunity = apps.get_model("opportunities", "ProviderOpportunity")
    missing = ProviderOpportunity.objects.filter(tokkobroker_property__isnull=True).values_list("id", flat=True)[:20]
    if missing:
        ids = ", ".join(str(i) for i in missing)
        raise RuntimeError(
            f"Cannot enforce tokkobroker_property as required; opportunities missing link: {ids}. "
            "Populate tokkobroker_property for all provider opportunities before migrating."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("opportunities", "0019_alter_provideropportunity_gross_commission_pct_and_more"),
    ]

    operations = [
        migrations.RunPython(ensure_no_null_tokkobroker, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="provideropportunity",
            name="tokkobroker_property",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="provider_opportunity",
                to="integrations.tokkobrokerproperty",
            ),
        ),
    ]
