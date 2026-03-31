from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .forms import XMLUploadForm
from .services import ProfStandartParser
import os
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from .models import Project, Task, Employee, EmployeeSkillProgress, LaborFunctionDetails, SkillLog, Notification
from django.db import models
from django.db.models import Q, Count, Sum
import glob
from .models import ParserSettings, Profession
from django.contrib import messages
from .services import EmployeeParser, ProjectTaskParser
from django.http import HttpResponse
from django.template.loader import get_template
import io
from django.contrib.staticfiles import finders

@staff_member_required
def sync_standards_view(request):
    settings = ParserSettings.objects.first()
    if not settings or not os.path.exists(settings.folder_path):
        messages.error(request, "Путь к папке не настроен в 'Настройках парсера' или не существует.")
        return redirect('admin:index')

    path_pattern = os.path.join(settings.folder_path, "*.xml")
    xml_files = glob.glob(path_pattern)
    
    new_count = 0
    skipped_count = 0
    
    for f_path in xml_files:
        parser = ProfStandartParser(f_path)
        result = parser.run()
        
        if result == 'created':
            new_count += 1
        elif result == 'exists':
            skipped_count += 1

    messages.success(request, f"Синхронизация завершена. Новых: {new_count}, Пропущено: {skipped_count}.")
    return redirect('admin:index')

@staff_member_required
def upload_standard_view(request):
    if request.method == 'POST':
        # Получаем список всех файлов из папки
        files = request.FILES.getlist('xml_files')
        
        if not files:
            messages.error(request, "Файлы не выбраны.")
            return redirect('upload_standard')

        success_count = 0
        errors = []

        for uploaded_file in files:
            # Проверяем, что это XML
            if not uploaded_file.name.endswith('.xml'):
                continue

            # Сохраняем временно
            temp_path = os.path.join(settings.MEDIA_ROOT, uploaded_file.name)
            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

            with open(temp_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)

            # Запускаем парсер для каждого файла
            try:
                parser = ProfStandartParser(temp_path)
                parser.run()
                success_count += 1
            except Exception as e:
                errors.append(f"Ошибка в файле {uploaded_file.name}: {str(e)}")
            finally:
                # Удаляем временный файл после парсинга
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        if success_count:
            messages.success(request, f"Успешно обработано файлов: {success_count}")
        if errors:
            for err in errors:
                messages.error(request, err)

        return redirect('upload_standard')

    return render(request, 'QualificationApp/upload.html')

@login_required
def manager_projects(request):
    try:
        manager_employee = request.user.employee
        projects = Project.objects.filter(manager=manager_employee)
    except AttributeError:
        projects = Project.objects.all()

    # Считаем задачи для каждого проекта
    for project in projects:
        counts = project.task_set.aggregate(
            todo=Count('id', filter=models.Q(status='todo')),
            progress=Count('id', filter=models.Q(status='in_progress')),
            done=Count('id', filter=models.Q(status='completed'))
        )
        project.stats = counts # Передаем статистику в объект проекта

    return render(request, 'QualificationApp/manager/projects.html', {'projects': projects})

@login_required
def task_detail(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    is_manager = (request.user.employee == task.project.manager) or request.user.is_superuser
    
    from .models import Profession, LaborFunctionDetails
    
    required_skills = task.required_skills.all()
    skills_count = required_skills.count()
    
    all_employees = Employee.objects.all()
    
    # Считаем процент соответствия для каждого сотрудника
    for emp in all_employees:
        if skills_count > 0:
            # Суммируем прогресс только по тем навыкам, которые нужны для задачи
            total_progress = EmployeeSkillProgress.objects.filter(
                employee=emp,
                skill_detail__in=required_skills
            ).aggregate(Sum('level'))['level__sum'] or 0
            
            # Рассчитываем среднее: сумма уровней / количество требуемых навыков
            emp.match_score = round(total_progress / skills_count, 1)
        else:
            emp.match_score = 0
    
    # Сортируем сотрудников: самые подходящие в начале списка
    all_employees = sorted(all_employees, key=lambda x: x.match_score, reverse=True)
    
    # Получаем ID уже выбранных навыков
    existing_skills_ids = list(task.required_skills.values_list('id', flat=True))
    
    all_professions = Profession.objects.prefetch_related(
        'generalizedlaborfunction_set__laborfunction_set__details' 
    ).all()
    
    return render(request, 'QualificationApp/manager/task_detail.html', {
        'task': task,
        'all_employees': all_employees,
        'all_professions': all_professions,
        'existing_skills_ids': existing_skills_ids,
        'is_manager': is_manager
    })

@login_required
def add_task_skill(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    # Проверка на руководителя
    if request.user.employee == task.project.manager or request.user.is_superuser:
        if request.method == 'POST':
            skill_id = request.POST.get('skill_id')
            if skill_id:
                skill = get_object_or_404(LaborFunctionDetails, id=skill_id)
                task.required_skills.add(skill)
    return redirect('task_detail', task_id=task_id)

@login_required
def remove_task_skill(request, task_id, skill_id):
    task = get_object_or_404(Task, id=task_id)
    # Проверка на руководителя
    if request.user.employee == task.project.manager or request.user.is_superuser:
        if request.method == 'POST':
            skill = get_object_or_404(LaborFunctionDetails, id=skill_id)
            task.required_skills.remove(skill)
    return redirect('task_detail', task_id=task_id)

def project_tasks(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    tasks = project.task_set.all()
    # Берем всех сотрудников
    free_employees = Employee.objects.all() 
    
    for task in tasks:
        req_skills = task.required_skills.all()
        task.recommended_emps = []
        
        if req_skills:
            for emp in free_employees:
                # Считаем навыки, освоенные хотя бы на 10% (уровень > 10)
                emp_skills_count = EmployeeSkillProgress.objects.filter(
                    employee=emp, 
                    skill_detail__in=req_skills, 
                    level__gte=10
                ).count()
                
                percent = int((emp_skills_count / req_skills.count()) * 100)
                task.recommended_emps.append({'emp': emp, 'percent': percent})
            
            task.recommended_emps.sort(key=lambda x: x['percent'], reverse=True)

    return render(request, 'QualificationApp/manager/tasks.html', {
        'project': project,
        'tasks': tasks,
    })

def assign_task(request, task_id):
    if request.method == 'POST':
        task = get_object_or_404(Task, id=task_id)
        employee_id = request.POST.get('employee_id')
        if employee_id:
            employee = get_object_or_404(Employee, id=employee_id)
            task.executor = employee
            task.status = Task.Status.IN_PROGRESS
            task.save()
    return redirect('project_tasks', project_id=task.project.id)

def rate_task(request, task_id):
    if request.method == 'POST':
        task = get_object_or_404(Task, id=task_id)
        # Получаем значение из кнопки (excellent, good или rework)
        action = request.POST.get('action') 
        
        if not action:
            return redirect('task_detail', task_id=task.id)

        # Логика для "На переделку"
        if action == 'rework':
            task.status = Task.Status.IN_PROGRESS
            task.grade = Task.Grade.REWORK
            task.save()
            messages.warning(request, f"Задача '{task.name}' отправлена на переделку.")
            return redirect('project_tasks', project_id=task.project.id)

        # Логика для успешного завершения (Отлично или Хорошо)
        task.status = Task.Status.COMPLETED
        task.grade = action # Присваиваем 'excellent' или 'good'
        task.save()

        # Определяем прогресс в зависимости от оценки
        increment = 10 if action == 'excellent' else 5
        
        if task.executor:
            for skill in task.required_skills.all():
                # Обновляем или создаем запись прогресса
                progress, created = EmployeeSkillProgress.objects.get_or_create(
                    employee=task.executor,
                    skill_detail=skill
                )
                
                # Повышаем уровень, но не выше 100
                old_level = progress.level
                progress.level = min(progress.level + increment, 100)
                progress.save()

                # Логируем изменение
                SkillLog.objects.create(
                    employee=task.executor,
                    skill_detail=skill,
                    level_reached=progress.level,
                    reason=f"Завершение задачи: {task.name} (Оценка: {task.get_grade_display()})"
                )
                
            if task.executor:
                status_text = "отправлена на переделку" if action == 'rework' else f"оценена на '{task.get_grade_display()}' и завершена"
                Notification.objects.create(
                    recipient=task.executor,
                    message=f"Ваша задача '{task.name}' была {status_text}."
                )

            messages.success(
                request, 
                f"Задача принята! Оценка: {task.get_grade_display()}. Навыки исполнителя повышены на {increment}%."
            )
                
    return redirect('project_tasks', project_id=task.project.id)

@login_required
def profile_view(request):
    employee = Employee.objects.filter(user=request.user).first()
    if not employee:
        return render(request, 'QualificationApp/profile.html', {'is_admin_only': True})

    skills_progress = EmployeeSkillProgress.objects.filter(employee=employee)
    
    for p in skills_progress:
        if p.level <= 1.0:
            p.display_percent = p.level * 100
        else:
            p.display_percent = p.level

    my_tasks = Task.objects.filter(executor=employee)
    
    return render(request, 'QualificationApp/profile.html', {
        'employee': employee,
        'skills_progress': skills_progress,
        'my_tasks': my_tasks
    })
    
def import_employees_view(request):
    if request.method == 'POST' and request.FILES.get('xml_file'):
        xml_file = request.FILES['xml_file']
        # Сохраняем временный файл
        temp_path = f"temp_{xml_file.name}"
        with open(temp_path, 'wb+') as destination:
            for chunk in xml_file.chunks():
                destination.write(chunk)
        
        parser = EmployeeParser(temp_path)
        result = parser.run()
        os.remove(temp_path) # Удаляем временный файл
        
        messages.success(request, f"Результат: {result}")
    return redirect('/admin/')

def import_projects_view(request):
    if request.method == 'POST' and request.FILES.get('xml_file'):
        xml_file = request.FILES['xml_file']
        temp_path = f"temp_{xml_file.name}"
        with open(temp_path, 'wb+') as destination:
            for chunk in xml_file.chunks():
                destination.write(chunk)
        
        parser = ProjectTaskParser(temp_path)
        result = parser.run()
        os.remove(temp_path)
        
        messages.success(request, f"Результат: {result}")
    return redirect('/admin/')

def submit_task_view(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    # Проверка: только исполнитель может отправить на проверку
    if task.executor and task.executor.user == request.user:
        task.status = Task.Status.TO_CONFIRM
        task.save()
        if task.project.manager:
            Notification.objects.create(
                recipient=task.project.manager,
                message=f"Задача '{task.name}' в проекте '{task.project.name}' выполнена и ждет вашей оценки."
            )
        messages.success(request, f"Задача '{task.name}' отправлена на проверку руководителю.")
    return redirect('profile')

def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, recipient__user=request.user)
    notification.is_read = True
    notification.save()
    return redirect(request.META.get('HTTP_REFERER', 'profile'))

def link_callback(uri, rel):
    result = finders.find(uri)
    if result:
        if not isinstance(result, (list, tuple)):
            result = [result]
        result = list(os.path.realpath(path) for path in result)
        path = result[0]
    else:
        s_url = settings.STATIC_URL
        s_root = settings.STATIC_ROOT
        m_url = settings.MEDIA_URL
        m_root = settings.MEDIA_ROOT

        if uri.startswith(m_url):
            path = os.path.join(m_root, uri.replace(m_url, ""))
        elif uri.startswith(s_url):
            path = os.path.join(s_root, uri.replace(s_url, ""))
        else:
            return uri

    if not os.path.isfile(path):
        raise Exception('media URI must help to find a valid file')
    return path
    
def skill_report_view(request):
    is_admin = request.user.is_staff
    # Пытаемся получить профиль сотрудника текущего пользователя
    current_employee = getattr(request.user, 'employee', None)

    # Логика доступа: админ выбирает любого, сотрудник — только себя
    if is_admin:
        employee_id = request.GET.get('employee')
    else:
        employee_id = current_employee.id if current_employee else None

    skill_id = request.GET.get('skill')
    
    # Базовый набор данных
    employees = Employee.objects.all() if is_admin else [current_employee]
    skills_in_logs = LaborFunctionDetails.objects.filter(id__in=SkillLog.objects.values('skill_detail_id')).distinct()

    logs = SkillLog.objects.all().order_by('-timestamp')
    if employee_id:
        logs = logs.filter(employee_id=employee_id)
    if skill_id:
        logs = logs.filter(skill_detail_id=skill_id)

    # Данные для графика
    chart_logs = logs.order_by('timestamp')
    chart_data = {
        'labels': [log.timestamp.strftime('%d.%m.%Y') for log in chart_logs],
        'values': [log.level_reached for log in chart_logs],
    }

    context = {
        'logs': logs,
        'employees': employees,
        'skills': skills_in_logs,
        'selected_employee': int(employee_id) if employee_id else None,
        'selected_skill': int(skill_id) if skill_id else None,
        'chart_data': chart_data,
        'is_admin': is_admin,
    }

    return render(request, 'reports/skill_report.html', context)



