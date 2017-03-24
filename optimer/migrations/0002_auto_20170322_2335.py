# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-22 23:35
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('optimer', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='optimer',
            name='details',
            field=models.CharField(default='', max_length=254),
        ),
        migrations.AlterField(
            model_name='optimer',
            name='doctrine',
            field=models.CharField(default='', max_length=254),
        ),
        migrations.AlterField(
            model_name='optimer',
            name='duration',
            field=models.CharField(default='', max_length=25),
        ),
        migrations.AlterField(
            model_name='optimer',
            name='fc',
            field=models.CharField(default='', max_length=254),
        ),
        migrations.AlterField(
            model_name='optimer',
            name='location',
            field=models.CharField(default='', max_length=254),
        ),
        migrations.AlterField(
            model_name='optimer',
            name='operation_name',
            field=models.CharField(default='', max_length=254),
        ),
        migrations.AlterField(
            model_name='optimer',
            name='system',
            field=models.CharField(default='', max_length=254),
        ),
    ]
