from django.db import migrations, models
from pgvector.django import VectorField


def create_vector_extension(apps, schema_editor):
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS vector;")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_vector_extension, migrations.RunPython.noop),
        migrations.AddField(
            model_name="document",
            name="text_extracted",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="DocumentChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chunk_index", models.IntegerField()),
                ("content", models.TextField()),
                ("embedding", VectorField(dimensions=1536, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("document", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="chunks", to="core.document")),
                ("project", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="chunks", to="core.project")),
            ],
        ),
        migrations.CreateModel(
            name="ExperimentCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content", models.TextField()),
                ("status", models.CharField(choices=[("generated", "generated"), ("running", "running"), ("done", "done"), ("error", "error")], default="generated", max_length=32)),
                ("stdout", models.TextField(blank=True, null=True)),
                ("stderr", models.TextField(blank=True, null=True)),
                ("artifacts", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("project", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="code_cells", to="core.project")),
            ],
        ),
        migrations.CreateModel(
            name="Plan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("project", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="plans", to="core.project")),
            ],
        ),
        migrations.CreateModel(
            name="Report",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("section", models.CharField(default="full", max_length=64)),
                ("content", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("project", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="reports", to="core.project")),
            ],
        ),
    ]

