# Generated manually for anonymous "deactivate new points" setting

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0035_alter_anonymous_show_all_points_help_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataset',
            name='anonymous_disable_new_points',
            field=models.BooleanField(
                default=False,
                help_text='When anonymous data input is enabled: anonymous contributors cannot create new geometry points; they can only open existing points and add or edit entries.',
            ),
        ),
    ]
