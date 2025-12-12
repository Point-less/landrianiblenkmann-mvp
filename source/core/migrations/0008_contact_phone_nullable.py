from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_agent_commission_split_nullable"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contact",
            name="phone_number",
            field=models.CharField(max_length=50, blank=True, null=True),
        ),
    ]
