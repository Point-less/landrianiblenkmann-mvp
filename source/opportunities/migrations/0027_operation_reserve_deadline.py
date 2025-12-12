from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("opportunities", "0026_operation_initial_offered_amount"),
    ]

    operations = [
        migrations.AddField(
            model_name="operation",
            name="reserve_deadline",
            field=models.DateField(blank=True, null=True, help_text="Deadline for the reserve amount (if applicable)."),
        ),
    ]
