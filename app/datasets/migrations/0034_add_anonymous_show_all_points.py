# Generated manually for anonymous map visibility setting

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0033_map_default_zoom_range_1_20'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataset',
            name='anonymous_show_all_points',
            field=models.BooleanField(
                default=False,
                help_text='When anonymous data input is enabled: show all geometry points on the map to anonymous contributors (not only their own). Editing stays limited to own points.',
            ),
        ),
    ]
