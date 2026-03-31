"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.urls import path, include
from QualificationApp.views import (
    upload_standard_view, 
    project_tasks,
    assign_task,
    rate_task,
    manager_projects,
    task_detail,
    profile_view,
    add_task_skill,
    remove_task_skill,
    sync_standards_view,
    import_employees_view,
    import_projects_view,
    submit_task_view,
    mark_notification_read,
    skill_report_view
)

urlpatterns = [
    path('admin/sync-standards/', sync_standards_view, name='sync_standards'),
    path('admin/import/employees/', import_employees_view),
    path('admin/import/projects/', import_projects_view),
    path('admin/upload-standard/', upload_standard_view, name='upload_standard'),
    path('manager/project/<int:project_id>/tasks/', project_tasks, name='project_tasks'),
    path('manager/task/<int:task_id>/assign/', assign_task, name='assign_task'),
    path('manager/task/<int:task_id>/rate/', rate_task, name='rate_task'),
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('manager/projects/', manager_projects, name='manager_projects'),
    path('manager/task/<int:task_id>/', task_detail, name='task_detail'),
    path('task/<int:task_id>/submit/', submit_task_view, name='submit_task'),
    path('profile/', profile_view, name='profile'),
    path('manager/task/<int:task_id>/add-skill/', add_task_skill, name='add_task_skill'),
    path('manager/task/<int:task_id>/remove-skill/<int:skill_id>/', remove_task_skill, name='remove_task_skill'),
    path('notification/read/<int:notification_id>/', mark_notification_read, name='mark_note_read'),
    path('report/skills/', skill_report_view, name='skill_report'),
]
