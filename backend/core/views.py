from django.contrib.auth import authenticate, get_user_model, login, logout
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction, connection
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
import json
import os
import uuid
from PyPDF2 import PdfReader
import boto3

from core.models import (
    Document,
    DocumentChunk,
    ExperimentCode,
    Plan,
    Project,
    Report,
    ResearchNote,
)


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
        extract_and_embed_document(doc)
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


# -------- Embeddings / Bedrock helpers --------


def get_bedrock_client():
    region = settings.BEDROCK_REGION
    return boto3.client("bedrock-runtime", region_name=region)


def embed_texts(texts):
    client = get_bedrock_client()
    payload = {"inputText": texts}
    response = client.invoke_model(
        modelId=settings.BEDROCK_EMBEDDING_MODEL,
        body=json.dumps(payload),
        accept="application/json",
        contentType="application/json",
    )
    result = json.loads(response["body"].read())
    return result.get("embedding")


def chunk_text(text, max_tokens=500, overlap=100):
    # naive char-based chunking approximating tokens
    chunk_size = max_tokens * 4
    overlap_size = overlap * 4
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        start = end - overlap_size
        if start < 0:
            start = 0
        if start == end:
            break
    return [c.strip() for c in chunks if c.strip()]


def extract_pdf_text(path):
    reader = PdfReader(path)
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def extract_and_embed_document(document: Document):
    local_path = default_storage.path(document.file.name)
    text = extract_pdf_text(local_path)
    chunks = chunk_text(text)
    DocumentChunk.objects.filter(document=document).delete()
    vectors = []
    for idx, chunk in enumerate(chunks):
        vec = embed_texts(chunk)
        vectors.append(
            DocumentChunk(
                project=document.project,
                document=document,
                chunk_index=idx,
                content=chunk,
                embedding=vec,
            )
        )
    DocumentChunk.objects.bulk_create(vectors)
    document.text_extracted = True
    document.save(update_fields=["text_extracted"])


# -------- Agent (plan/code/report) --------


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

    chunks = (
        DocumentChunk.objects.filter(project=project)
        .order_by("chunk_index")[:20]
        .values_list("content", flat=True)
    )
    if not chunks:
        return JsonResponse({"error": "no embedded documents for this project"}, status=400)

    context_snippets = "\n\n".join(chunks)

    plan_prompt = f"""
You are an end-to-end research agent. Given the research goal and evidence snippets, propose a concise, actionable plan with numbered steps (short sentences).

Goal:
{goal}

Evidence:
{context_snippets[:6000]}

Return JSON with fields: plan (array of steps), summary (string).
"""
    plan_resp = call_text_model(plan_prompt)
    plan_json = try_parse_json(plan_resp) or {"plan": plan_resp, "summary": plan_resp}
    plan_obj = Plan.objects.create(project=project, content=plan_json)

    code_prompt = f"""
You are an ML/analysis assistant. Given a research plan, propose Python experiment code (concise). Use pandas/numpy/matplotlib only. Assume data comes from uploaded PDFs; you may sketch data loading but keep it minimal.

Plan:
{json.dumps(plan_json, indent=2)}

Return JSON with fields: code (string), notes (string).
"""
    code_resp = call_text_model(code_prompt)
    code_json = try_parse_json(code_resp) or {"code": code_resp, "notes": ""}
    code_obj = ExperimentCode.objects.create(
        project=project,
        content=code_json.get("code", code_resp),
        status="generated",
        stdout="",
        stderr=code_json.get("notes", ""),
    )

    report_prompt = f"""
Draft a short research brief (2-3 paragraphs) based on the goal and plan. Do not fabricate results. Emphasize next steps and expected outcomes.

Goal:
{goal}

Plan:
{json.dumps(plan_json, indent=2)}
"""
    report_resp = call_text_model(report_prompt)
    Report.objects.create(project=project, section="brief", content=report_resp)

    return JsonResponse(
        {
            "plan": plan_json,
            "code": {"id": code_obj.id, "content": code_obj.content, "status": code_obj.status},
            "report": {"section": "brief", "content": report_resp},
        }
    )


def call_text_model(prompt: str) -> str:
    client = get_bedrock_client()
    body = {"messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}], "max_tokens": 800}
    resp = client.invoke_model(
        modelId=settings.BEDROCK_TEXT_MODEL,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    data = json.loads(resp["body"].read())
    # Anthropic style
    if isinstance(data, dict):
        if "output_text" in data:
            return data["output_text"]
        if "content" in data and isinstance(data["content"], list):
            return "".join(part.get("text", "") for part in data["content"] if isinstance(part, dict))
        if "completion" in data:
            return data["completion"]
    return str(data)


def try_parse_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None


