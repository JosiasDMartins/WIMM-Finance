# Generated migration file for adding realized field to Transaction model
# Save this file as: finances/migrations/0002_transaction_realized.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finances', '0008_alter_investment_date_created'),
    ]

    operations = [
        # This migration is redundant with 0006_transaction_realized
        # Kept for migration history consistency, but does nothing
        # The field is already added by 0006
    ]
