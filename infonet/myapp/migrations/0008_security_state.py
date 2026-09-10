from django.db import migrations


def seed(apps, schema_editor):
    apps.get_model('myapp', 'SecurityState').objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [('myapp', '0007_security_limits')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
