from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_vector_and_agent"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="documentchunk",
            index=models.Index(fields=["project", "document", "chunk_index"], name="doc_chunk_idx"),
        ),
    ]

