# Anonymous show all mapping areas outlines on data-input map

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0036_add_anonymous_disable_new_points'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataset',
            name='anonymous_show_all_mapping_areas',
            field=models.BooleanField(
                default=False,
                help_text='When anonymous data input and mapping areas are enabled: show all mapping area outlines (with names) on the anonymous data-input map. Does not grant anonymous mapping-area editing.',
            ),
        ),
    ]
