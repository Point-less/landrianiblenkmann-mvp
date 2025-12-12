from django.db import migrations


def backfill_values(apps, schema_editor):
    ProviderOpportunity = apps.get_model("opportunities", "ProviderOpportunity")
    for opp in ProviderOpportunity.objects.select_related("source_intention__valuation"):
        val = getattr(opp.source_intention, "valuation", None)
        if val:
            opp.valuation_test_value = val.test_value
            opp.valuation_close_value = val.close_value
            opp.save(update_fields=["valuation_test_value", "valuation_close_value"])


class Migration(migrations.Migration):

    dependencies = [
        ("opportunities", "0034_provideropportunity_valuation_values"),
    ]

    operations = [
        migrations.RunPython(backfill_values, migrations.RunPython.noop),
    ]
