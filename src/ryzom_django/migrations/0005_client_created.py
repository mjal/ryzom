# Generated by Django 3.1.7 on 2021-03-11 07:32

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('ryzom_django', '0004_registration'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='created',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
