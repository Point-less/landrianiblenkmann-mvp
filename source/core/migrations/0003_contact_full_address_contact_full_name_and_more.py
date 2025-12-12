from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_remove_tokkobrokerproperty"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="full_address",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="contact",
            name="full_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="contact",
            name="tax_condition",
            field=models.CharField(
                blank=True,
                choices=[
                    ("ri", "Responsable Inscripto"),
                    ("monotributo", "Monotributo"),
                    ("exento", "Exento"),
                    ("consumidor_final", "Consumidor final"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="contact",
            name="tax_id",
            field=models.CharField(blank=True, max_length=20, verbose_name="CUIT/CUIL"),
        ),
        migrations.AddField(
            model_name="property",
            name="full_address",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
