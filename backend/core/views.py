from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone

from core.models import Document, Project, ResearchNote


def health(request):
    return JsonResponse({"status": "ok", "app": "e2era"})


def hello(request):
    return JsonResponse({"message": "Hello from E2ERA backend"})


@csrf_exempt
@require_POST
def login_view(request):
    username = request.POST.get("username")
    password = request.POST.get("password")
    if not username or not password:
        return JsonResponse({"error": "username and password required"}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"error": "invalid credentials"}, status=401)

    login(request, user)
    return JsonResponse({"ok": True, "user": {"username": user.username}})


@csrf_exempt
@require_POST
def logout_view(request):
    logout(request)
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def register_view(request):
    username = request.POST.get("username")
    password = request.POST.get("password")
    email = request.POST.get("email", "")

    if not username or not password:
        return JsonResponse({"error": "username and password required"}, status=400)

    User = get_user_model()
    if User.objects.filter(username=username).exists():
        return JsonResponse({"error": "username already exists"}, status=400)

    user = User.objects.create_user(username=username, password=password, email=email)
    login(request, user)
    return JsonResponse({"ok": True, "user": {"username": user.username, "email": user.email}})


def me(request):
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False}, status=401)
    return JsonResponse(
        {
            "authenticated": True,
            "user": {
                "username": request.user.username,
                "email": request.user.email,
            },
        }
    )


def _project_payload(project: Project):
    return {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "created_at": project.created_at.isoformat(),
        "documents": [
            {
                "id": doc.id,
                "name": doc.original_name or doc.file.name,
                "url": doc.file.url,
                "uploaded_at": doc.uploaded_at.isoformat(),
            }
            for doc in project.documents.order_by("-uploaded_at")
        ],
        "notes": [
            {"id": note.id, "content": note.content, "created_at": note.created_at.isoformat()}
            for note in project.notes.order_by("-created_at")
        ],
    }


@csrf_exempt
def projects_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "unauthorized"}, status=401)

    if request.method == "GET":
        projects = Project.objects.filter(owner=request.user).order_by("-created_at")
        return JsonResponse({"projects": [_project_payload(p) for p in projects]})

    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description", "")
        if not title:
            return JsonResponse({"error": "title required"}, status=400)
        project = Project.objects.create(owner=request.user, title=title, description=description)
        return JsonResponse({"project": _project_payload(project)}, status=201)

    return JsonResponse({"error": "method not allowed"}, status=405)


@csrf_exempt
def project_detail(request, project_id: int):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "unauthorized"}, status=401)
    try:
        project = Project.objects.get(id=project_id, owner=request.user)
    except Project.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    if request.method == "GET":
        return JsonResponse({"project": _project_payload(project)})

    return JsonResponse({"error": "method not allowed"}, status=405)


@csrf_exempt
def project_upload(request, project_id: int):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "unauthorized"}, status=401)
    try:
        project = Project.objects.get(id=project_id, owner=request.user)
    except Project.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    file = request.FILES.get("file")
    if not file:
        return JsonResponse({"error": "file required"}, status=400)

    # Save file
    stored_path = default_storage.save(file.name, file)
    doc = Document.objects.create(
        project=project,
        file=stored_path,
        original_name=file.name,
        uploaded_at=timezone.now(),
    )
    return JsonResponse({"document": {
        "id": doc.id,
        "name": doc.original_name or doc.file.name,
        "url": doc.file.url,
        "uploaded_at": doc.uploaded_at.isoformat(),
    }}, status=201)


@csrf_exempt
def project_note(request, project_id: int):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "unauthorized"}, status=401)
    try:
        project = Project.objects.get(id=project_id, owner=request.user)
    except Project.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    content = request.POST.get("content", "").strip()
    if not content:
        return JsonResponse({"error": "content required"}, status=400)

    note = ResearchNote.objects.create(project=project, content=content)
    return JsonResponse({"note": {"id": note.id, "content": note.content, "created_at": note.created_at.isoformat()}}, status=201)


