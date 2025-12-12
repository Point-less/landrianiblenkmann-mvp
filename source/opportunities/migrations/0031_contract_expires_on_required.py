from django.db import migrations, models
from django.utils import timezone


def backfill_contract_expiration(apps, schema_editor):
    ProviderOpportunity = apps.get_model("opportunities", "ProviderOpportunity")
    for opp in ProviderOpportunity.objects.filter(contract_expires_on__isnull=True):
        opp.contract_expires_on = timezone.now().date()
        opp.save(update_fields=["contract_expires_on"])


class Migration(migrations.Migration):

    dependencies = [
        ("opportunities", "0030_enforce_reserve_required"),
    ]

    operations = [
        migrations.RunPython(backfill_contract_expiration, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="provideropportunity",
            name="contract_expires_on",
            field=models.DateField(),
        ),
    ]
