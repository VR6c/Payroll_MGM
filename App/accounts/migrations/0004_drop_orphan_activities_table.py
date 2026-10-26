from django.db import migrations


def drop_orphan_activities_table(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS activities_activity;")
        cursor.execute("DELETE FROM django_migrations WHERE app = 'activities';")


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_seed_default_roles'),
    ]

    operations = [
        migrations.RunPython(drop_orphan_activities_table, migrations.RunPython.noop),
    ]
