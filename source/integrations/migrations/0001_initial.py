from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('core', '0002_remove_tokkobrokerproperty'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='TokkobrokerProperty',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('tokko_id', models.PositiveIntegerField(unique=True)),
                        ('ref_code', models.CharField(max_length=64)),
                        ('address', models.CharField(blank=True, max_length=255)),
                        ('tokko_created_at', models.DateField(blank=True, null=True)),
                    ],
                    options={
                        'ordering': ('-created_at',),
                        'verbose_name': 'Tokkobroker property',
                        'verbose_name_plural': 'Tokkobroker properties',
                        'db_table': 'core_tokkobrokerproperty',
                    },
                ),
            ],
        ),
    ]
