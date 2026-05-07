from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0038_dataset_data_input_attachments_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="datasetfield",
            name="anonymous_welcome",
            field=models.BooleanField(
                default=False,
                help_text="When anonymous data input is enabled: show this field in the welcome modal under Your name.",
            ),
        ),
        migrations.AddField(
            model_name="virtualcontributor",
            name="welcome_field_values",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Answers from anonymous welcome modal, keyed by DatasetField.field_name",
            ),
        ),
    ]
