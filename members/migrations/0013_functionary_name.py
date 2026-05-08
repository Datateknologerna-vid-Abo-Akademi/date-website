from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0012_github_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='functionary',
            name='name',
            field=models.CharField(blank=True, max_length=200, verbose_name='Namn'),
        ),
        migrations.AlterField(
            model_name='functionary',
            name='member',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='members.member',
                verbose_name='Medlem',
            ),
        ),
    ]
