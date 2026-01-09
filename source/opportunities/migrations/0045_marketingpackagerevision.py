from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("opportunities", "0044_alter_provideropportunity_source_intention_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketingPackageRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                ("headline", models.CharField(blank=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("price", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("state", models.CharField(choices=[("preparing", "Preparing"), ("published", "Published"), ("paused", "Paused")], max_length=20)),
                ("features", models.JSONField(blank=True, default=list)),
                ("media_assets", models.JSONField(blank=True, default=list)),
                ("currency", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="core.currency")),
                ("package", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revisions", to="opportunities.marketingpackage")),
            ],
            options={
                "ordering": ("-package_id", "-version"),
                "verbose_name": "marketing package revision",
                "verbose_name_plural": "marketing package revisions",
            },
        ),
    ]
