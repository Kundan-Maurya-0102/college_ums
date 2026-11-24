from django.urls import path

from . import views

app_name = "platform"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("colleges/", views.college_list, name="colleges"),
    path("colleges/new/", views.college_create, name="college_create"),
    path("colleges/<int:pk>/", views.college_detail, name="college_detail"),
    path("colleges/<int:pk>/suspend/", views.college_suspend, name="college_suspend"),
    path("colleges/<int:pk>/resume/", views.college_resume, name="college_resume"),
    path("colleges/<int:pk>/backup/", views.college_backup, name="college_backup"),
    path("plans/", views.plan_list, name="plans"),
    path("plans/new/", views.plan_create, name="plan_create"),
    path("plans/<int:pk>/", views.plan_edit, name="plan_edit"),
    path("usage/", views.usage_report, name="usage"),
    path("tickets/", views.ticket_list, name="tickets"),
    path("tickets/new/", views.ticket_create, name="ticket_create"),
    path("tickets/<int:pk>/", views.ticket_detail, name="ticket_detail"),
]
