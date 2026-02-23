from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("foodbackend", "0005_address_latitude_address_longitude"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="item",
            name="is_combo",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="ComboItem",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=1)),
                (
                    "combo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="combo_links",
                        to="foodbackend.item",
                    ),
                ),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="combo_components",
                        to="foodbackend.item",
                    ),
                ),
            ],
            options={
                "unique_together": {("combo", "item")},
            },
        ),
        migrations.AddField(
            model_name="item",
            name="combo_items",
            field=models.ManyToManyField(
                blank=True,
                related_name="included_in_combos",
                symmetrical=False,
                through="foodbackend.ComboItem",
                to="foodbackend.item",
            ),
        ),
    ]
