from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("intentions", "0006_simplify_seeker_states"),
    ]

    operations = [
        migrations.RenameField(
            model_name="saleproviderintention",
            old_name="documentation_notes",
            new_name="notes",
        ),
    ]
