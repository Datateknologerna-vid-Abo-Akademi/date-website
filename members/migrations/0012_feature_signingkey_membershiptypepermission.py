from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0011_delete_alumniemailrecipient_delete_alumnisignup'),
    ]

    operations = [
        migrations.CreateModel(
            name='Feature',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codename', models.CharField(max_length=100, unique=True, verbose_name='Kodnamn')),
                ('name', models.CharField(max_length=200, verbose_name='Namn')),
            ],
            options={
                'verbose_name': 'Funktion',
                'verbose_name_plural': 'Funktioner',
            },
        ),
        migrations.CreateModel(
            name='SigningKey',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kid', models.CharField(max_length=64, unique=True)),
                ('private_key_pem', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Signeringsnyckel',
                'verbose_name_plural': 'Signeringsnycklar',
            },
        ),
        migrations.CreateModel(
            name='MembershipTypePermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('membership_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='feature_permissions',
                    to='members.membershiptype',
                    verbose_name='Medlemskapstyp',
                )),
                ('feature', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='members.feature',
                    verbose_name='Funktion',
                )),
            ],
            options={
                'verbose_name': 'Behörighet',
                'verbose_name_plural': 'Behörigheter',
                'unique_together': {('membership_type', 'feature')},
            },
        ),
    ]
