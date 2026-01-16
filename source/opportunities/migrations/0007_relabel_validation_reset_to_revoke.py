from django.db import migrations


def relabel_reset_to_revoke(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    FSMStateTransition = apps.get_model("utils", "FSMStateTransition")

    try:
        validation_ct = ContentType.objects.get(app_label="opportunities", model="validation")
    except ContentType.DoesNotExist:
        return

    FSMStateTransition.objects.filter(
        content_type=validation_ct,
        transition="reset",
    ).update(transition="revoke")

class Migration(migrations.Migration):
    dependencies = [
        ("opportunities", "0006_provideropportunity_tokkobroker_property"),
        ("utils", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(relabel_reset_to_revoke, migrations.RunPython.noop),
    ]

