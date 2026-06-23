# Generated manually for Notice link field
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('quiz_app', '0026_alter_badge_requirement_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='notice',
            name='link',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
