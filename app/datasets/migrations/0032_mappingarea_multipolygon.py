# PolygonField -> MultiPolygonField (PostGIS ST_Multi)

import django.contrib.gis.db.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0031_add_map_default_coordinates'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE datasets_mappingarea
                    ALTER COLUMN geometry TYPE geometry(MultiPolygon,4326)
                    USING ST_Multi(geometry::geometry);
                    """,
                    reverse_sql="""
                    ALTER TABLE datasets_mappingarea
                    ALTER COLUMN geometry TYPE geometry(Polygon,4326)
                    USING ST_GeometryN(geometry, 1);
                    """,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='mappingarea',
                    name='geometry',
                    field=django.contrib.gis.db.models.fields.MultiPolygonField(srid=4326),
                ),
            ],
        ),
    ]
