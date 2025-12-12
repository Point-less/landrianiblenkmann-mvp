from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_agent_commission_split"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="contact",
            name="full_name",
        ),
        migrations.AlterField(
            model_name="contact",
            name="email",
            field=models.EmailField(max_length=254, blank=False),
        ),
    ]
