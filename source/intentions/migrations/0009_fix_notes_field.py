from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("intentions", "0008_merge_0006_0007"),
    ]

    operations = [
        migrations.RunSQL(
            """
            ALTER TABLE intentions_saleproviderintention
            ADD COLUMN IF NOT EXISTS notes text;
            """,
            reverse_sql="""
            ALTER TABLE intentions_saleproviderintention
            ADD COLUMN IF NOT EXISTS documentation_notes text;
            """,
        ),
    ]
