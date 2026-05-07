# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0039_anonymous_welcome_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="dataset",
            name="data_input_show_street_view",
            field=models.BooleanField(
                default=True,
                help_text="When enabled, contributors see a Street View button in the geometry detail panel on the data-input map.",
            ),
        ),
    ]
