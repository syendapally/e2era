from django.conf import settings
from django.db import models


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

