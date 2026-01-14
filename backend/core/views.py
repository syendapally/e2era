from django.contrib.auth import authenticate, get_user_model, login, logout
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
import json
import os
import uuid
import logging
import traceback

logger = logging.getLogger(__name__)

from core.models import (
    Document,
    DocumentChunk,
    ExperimentCode,
    Plan,
    Project,
    Report,
    ResearchNote,
)
from llm.ingest import embed_document
from llm.agent import run_agent_pipeline
from ml_models.fraud_model import get_fraud_model, model_feature_info


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

    # Extract and embed in background-ish (inline for now)
    try:
        embed_document(doc)
    except Exception as exc:  # pragma: no cover - best-effort
        return JsonResponse({"error": f"upload succeeded but embedding failed: {exc}"}, status=500)

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


def latest_agent_payload(project: Project):
    answer = project.reports.filter(section="answer").order_by("-created_at").first()
    code = project.code_cells.order_by("-created_at").first()
    return {
        "answer": answer.content if answer else None,
        "code": {
            "id": code.id,
            "content": code.content,
            "status": code.status,
            "stdout": code.stdout,
            "stderr": code.stderr,
        } if code else None,
        "exec": {
            "stdout": code.stdout,
            "stderr": code.stderr,
        } if code else None,
    }


# -------- Agent (plan only for now) --------


@csrf_exempt
def run_agent(request, project_id: int):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "unauthorized"}, status=401)
    try:
        project = Project.objects.get(id=project_id, owner=request.user)
    except Project.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    goal = (
        ResearchNote.objects.filter(project=project)
        .order_by("-created_at")
        .values_list("content", flat=True)
        .first()
        or "Research the topic based on uploaded documents."
    )

    # ReAct agent (retrieve + run_code tools); final answer from LLM
    try:
        result = run_agent_pipeline(project.id, goal) or {}
    except Exception as exc:  # pragma: no cover - defensive surface for frontend UX
        # Log full traceback to help debug runtime errors
        logger.exception("run_agent failed")
        return JsonResponse({"error": f"agent failed: {exc}"}, status=500)

    answer = result.get("answer")
    code = result.get("code")
    exec_out = result.get("exec")

    if answer:
        Report.objects.create(project=project, section="answer", content=answer)
    if code:
        ExperimentCode.objects.create(
            project=project,
            content=code,
            status="done" if (exec_out and not exec_out.get("stderr")) else "error" if exec_out else "generated",
            stdout=exec_out.get("stdout") if exec_out else "",
            stderr=exec_out.get("stderr") if exec_out else "",
        )
    return JsonResponse(
        {
            "answer": answer,
            "code": code,
            "exec": exec_out,
        }
    )


def agent_data(request, project_id: int):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "unauthorized"}, status=401)
    try:
        project = Project.objects.get(id=project_id, owner=request.user)
    except Project.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    if request.method != "GET":
        return JsonResponse({"error": "method not allowed"}, status=405)

    return JsonResponse(latest_agent_payload(project))


# -------- Fraud model (XGBoost) --------


@csrf_exempt
def fraud_model_details(request):
    if request.method != "GET":
        return JsonResponse({"error": "method not allowed"}, status=405)
    try:
        model = get_fraud_model()
    except Exception as exc:
        logger.exception("Failed to load fraud model")
        return JsonResponse({"error": f"model unavailable: {exc}"}, status=500)

    return JsonResponse(
        {
            "features": model_feature_info(),
            "model_columns": model.feature_columns,
            "training_metrics": model.training_metrics,
            "artifact": "ml_models/artifacts/fraud_xgb.joblib",
        }
    )


@csrf_exempt
@require_POST
def fraud_predict(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload.")

    claims = payload.get("claims") if isinstance(payload, dict) else None
    if claims is None and isinstance(payload, dict):
        # Allow a single claim object without wrapping it in an array
        claims = [payload]

    if not claims or not isinstance(claims, list):
        return HttpResponseBadRequest("Provide a 'claims' array or a single claim object.")

    try:
        model = get_fraud_model()
        probs = model.predict_proba(claims)
        predictions = [
            {
                "fraud_probability": p,
                "label": "fraud" if p >= 0.5 else "legit",
            }
            for p in probs
        ]
    except Exception as exc:
        logger.exception("Fraud prediction failed")
        return JsonResponse({"error": f"prediction failed: {exc}"}, status=500)

    return JsonResponse(
        {
            "predictions": predictions,
            "threshold": 0.5,
            "feature_hint": [f["name"] for f in model_feature_info()],
        }
    )

