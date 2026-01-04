from django.conf import settings
from django.db import models
from pgvector.django import VectorField


class Project(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - for admin/debug
        return f"{self.title} ({self.owner})"


class Document(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="documents"
    )
    file = models.FileField(upload_to="documents/")
    original_name = models.CharField(max_length=512, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    text_extracted = models.BooleanField(default=False)

    def __str__(self) -> str:  # pragma: no cover
        return self.original_name or self.file.name


class ResearchNote(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="notes"
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover
        return self.content[:40]


class DocumentChunk(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="chunks"
    )
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="chunks"
    )
    chunk_index = models.IntegerField()
    content = models.TextField()
    embedding = VectorField(dimensions=1536, null=True)  # titan embed dim
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["project", "document", "chunk_index"]),
        ]


class Plan(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="plans")
    content = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class ExperimentCode(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="code_cells"
    )
    content = models.TextField()
    status = models.CharField(
        max_length=32,
        choices=[("generated", "generated"), ("running", "running"), ("done", "done"), ("error", "error")],
        default="generated",
    )
    stdout = models.TextField(blank=True, null=True)
    stderr = models.TextField(blank=True, null=True)
    artifacts = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Report(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="reports")
    section = models.CharField(max_length=64, default="full")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

