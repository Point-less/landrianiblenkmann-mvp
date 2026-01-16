from django.db import migrations


def rename_marketing_package_states(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    FSMStateTransition = apps.get_model("utils", "FSMStateTransition")
    MarketingPackage = apps.get_model("opportunities", "MarketingPackage")

    state_map = {
        "available": "published",
    }
    transition_map = {
        "reserve": "pause",
        "release": "publish",
    }

    # Update existing MarketingPackage rows
    for old, new in state_map.items():
        MarketingPackage.objects.filter(state=old).update(state=new)

    # Update our custom transition log
    try:
        mp_ct = ContentType.objects.get(app_label="opportunities", model="marketingpackage")
    except ContentType.DoesNotExist:
        mp_ct = None

    if mp_ct:
        for old, new in transition_map.items():
            FSMStateTransition.objects.filter(content_type=mp_ct, transition=old).update(transition=new)
        for old, new in state_map.items():
            FSMStateTransition.objects.filter(content_type=mp_ct, from_state=old).update(from_state=new)
            FSMStateTransition.objects.filter(content_type=mp_ct, to_state=old).update(to_state=new)

class Migration(migrations.Migration):
    dependencies = [
        ("opportunities", "0007_relabel_validation_reset_to_revoke"),
        ("utils", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(rename_marketing_package_states, migrations.RunPython.noop),
    ]

