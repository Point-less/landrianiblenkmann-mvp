from __future__ import annotations

from django.db import migrations, models
from django.db.models import Q


def migrate_revisions_into_packages(apps, schema_editor):
    MarketingPackage = apps.get_model("opportunities", "MarketingPackage")
    MarketingPackageRevision = apps.get_model("opportunities", "MarketingPackageRevision")

    for package in MarketingPackage.objects.all().iterator():
        revisions = list(
            MarketingPackageRevision.objects.filter(package=package).order_by("version")
        )

        if not revisions:
            package.version = 1
            package.is_active = True
            package.save(update_fields=["version", "is_active", "updated_at"])
            continue

        active_rev = next((rev for rev in revisions if rev.is_active), revisions[-1])

        # Update the existing package row to represent the active revision
        MarketingPackage.objects.filter(pk=package.pk).update(
            version=active_rev.version or 1,
            is_active=True,
            state=active_rev.state,
            headline=active_rev.headline,
            description=active_rev.description,
            price=active_rev.price,
            currency_id=active_rev.currency_id,
            features=active_rev.features,
            media_assets=active_rev.media_assets,
            updated_at=active_rev.updated_at,
        )

        # Create rows for the inactive revisions
        for rev in revisions:
            if rev.pk == active_rev.pk:
                continue
            new_pkg = MarketingPackage.objects.create(
                opportunity=package.opportunity,
                version=rev.version or 1,
                is_active=rev.is_active,
                state=rev.state,
                headline=rev.headline,
                description=rev.description,
                price=rev.price,
                currency_id=rev.currency_id,
                features=rev.features,
                media_assets=rev.media_assets,
                created_at=rev.created_at,
                updated_at=rev.updated_at,
            )
            # Ensure timestamps are preserved even with auto_now fields
            MarketingPackage.objects.filter(pk=new_pkg.pk).update(
                created_at=rev.created_at,
                updated_at=rev.updated_at,
            )


def noop_reverse(apps, schema_editor):
    # Irreversible migration
    pass


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("opportunities", "0046_alter_marketingpackagerevision_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="marketingpackage",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="marketingpackage",
            name="version",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.RunPython(migrate_revisions_into_packages, reverse_code=noop_reverse),
        migrations.DeleteModel(
            name="MarketingPackageRevision",
        ),
        migrations.AddConstraint(
            model_name="marketingpackage",
            constraint=models.UniqueConstraint(
                fields=["opportunity", "version"],
                name="uniq_marketing_package_version_per_opportunity",
            ),
        ),
        migrations.AddConstraint(
            model_name="marketingpackage",
            constraint=models.UniqueConstraint(
                fields=["opportunity"],
                condition=Q(is_active=True),
                name="uniq_active_marketing_package_per_opportunity",
            ),
        ),
    ]
