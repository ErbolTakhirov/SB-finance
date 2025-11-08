from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64, unique=True)),
            ],
        ),
        migrations.AddField(
            model_name='document',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='documents', to='core.tag'),
        ),
        migrations.AddField(
            model_name='expense',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='expenses', to='core.tag'),
        ),
        migrations.AddField(
            model_name='income',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='incomes', to='core.tag'),
        ),
    ]


