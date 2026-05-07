from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0037_add_anonymous_show_all_mapping_areas"),
    ]

    operations = [
        migrations.AddField(
            model_name="dataset",
            name="data_input_attachments_mode",
            field=models.CharField(
                choices=[
                    ("images", "images"),
                    ("audio", "audio"),
                    ("images_audio", "images and audio"),
                    ("none", "none"),
                ],
                default="images",
                help_text="Which file types can be attached to entries in the data input view (per selected entry).",
                max_length=32,
            ),
        ),
    ]
