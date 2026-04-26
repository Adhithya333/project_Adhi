# Generated migration - Migrate coordinator users to staff

from django.db import migrations


def migrate_coordinator_to_staff(apps, schema_editor):
    """Convert all coordinator users to staff."""
    User = apps.get_model('accounts', 'User')
    User.objects.filter(user_type='coordinator').update(user_type='staff')


def reverse_migrate(apps, schema_editor):
    """Reverse: convert staff back to coordinator (for rollback only)."""
    pass  # Cannot reliably reverse - would need to know which staff were originally coordinators


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_delete_invitetoken'),
    ]

    operations = [
        migrations.RunPython(migrate_coordinator_to_staff, reverse_migrate),
    ]
