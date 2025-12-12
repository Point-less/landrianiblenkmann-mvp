from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("intentions", "0009_fix_notes_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="salevaluation",
            name="valuation_date",
            field=models.DateField(blank=True, null=True, help_text="Date the valuation was issued."),
        ),
    ]
