# Generated by Django 4.1.3 on 2024-11-28 09:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0008_alter_radicacion_convenio'),
    ]

    operations = [
        migrations.AddField(
            model_name='radicacion',
            name='visto',
            field=models.BooleanField(default=False),
        ),
    ]
