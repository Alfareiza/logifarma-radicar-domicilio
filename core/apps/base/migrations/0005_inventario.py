# Generated by Django 4.1.3 on 2023-09-21 07:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0004_alter_med_controlado_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='Inventario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('centro', models.CharField(max_length=24)),
                ('cod_mol', models.CharField(max_length=24)),
                ('cod_barra', models.CharField(max_length=128)),
                ('cum', models.CharField(blank=True, max_length=64, null=True)),
                ('descripcion', models.CharField(max_length=250)),
                ('lote', models.CharField(max_length=24)),
                ('fecha_vencimiento', models.DateField()),
                ('inventario', models.IntegerField()),
                ('costo_promedio', models.IntegerField()),
                ('cantidad_empaque', models.IntegerField()),
            ],
        ),
    ]