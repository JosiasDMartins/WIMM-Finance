# Generated migration file for adding realized field to Transaction model
# Save this file as: finances/migrations/0002_transaction_realized.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finances', '0001_initial'),  # Adjust this to match your last migration
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='realized',
            field=models.BooleanField(default=False, help_text='Whether this transaction has been consolidated/completed'),
        ),
    ]
