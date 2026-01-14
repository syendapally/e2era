from django.urls import path

from core import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("hello/", views.hello, name="hello"),
    path("auth/login/", views.login_view, name="login"),
    path("auth/logout/", views.logout_view, name="logout"),
    path("auth/register/", views.register_view, name="register"),
    path("auth/me/", views.me, name="me"),
    path("projects/", views.projects_view, name="projects"),
    path("projects/<int:project_id>/", views.project_detail, name="project-detail"),
    path("projects/<int:project_id>/upload/", views.project_upload, name="project-upload"),
    path("projects/<int:project_id>/notes/", views.project_note, name="project-note"),
    path("projects/<int:project_id>/agent/run/", views.run_agent, name="project-agent-run"),
    path("projects/<int:project_id>/agent/data/", views.agent_data, name="project-agent-data"),
    path("fraud/model/", views.fraud_model_details, name="fraud-model-details"),
    path("fraud/predict/", views.fraud_predict, name="fraud-predict"),
]


