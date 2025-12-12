from django.db import migrations


def collapse_states(apps, schema_editor):
    SaleSeekerIntention = apps.get_model("intentions", "SaleSeekerIntention")
    SaleSeekerIntention.objects.exclude(state="converted").update(state="qualifying")


class Migration(migrations.Migration):

    dependencies = [
        ("intentions", "0005_operation_type_not_null"),
    ]

    operations = [
        migrations.RunPython(collapse_states, migrations.RunPython.noop),
    ]
