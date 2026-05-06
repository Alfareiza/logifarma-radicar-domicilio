from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0017_prescriptionocrtransaction_saparticle_searchbarra_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='radicacion',
            index=models.Index(
                fields=['-datetime', '-id'],
                name='rad_sin_acta_nav_idx',
                condition=models.Q(acta_entrega__isnull=True),
            ),
        ),
    ]
