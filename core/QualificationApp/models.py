from django.db import models
from django.db import transaction
from django.contrib.auth.models import User


class Profession(models.Model):
    code = models.CharField(max_length=20)
    name = models.TextField()
    publish_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.code} {self.name[:50]}"
    class Meta:
        verbose_name = "Профессия"
        verbose_name_plural = "Профессии"

class GeneralizedLaborFunction(models.Model):
    profession = models.ForeignKey(Profession, on_delete=models.CASCADE)
    code = models.CharField(max_length=20)
    name = models.TextField()
    def __str__(self):
        return f"{self.code} {self.name[:50]}"
    class Meta:
        verbose_name = "ОТФ"
        verbose_name_plural = "Обобщенные трудовые функции"

class LaborFunction(models.Model):
    generalized_function = models.ForeignKey(GeneralizedLaborFunction, on_delete=models.CASCADE)
    code = models.CharField(max_length=20)
    name = models.TextField()
    def __str__(self):
        return f"{self.code} {self.name[:50]}"
    class Meta:
        verbose_name = "Трудовая функция"
        verbose_name_plural = "Трудовые функции"

class LaborFunctionDetails(models.Model):
    class DetailType(models.TextChoices):
        KNOWLEDGE = 'KNOW', 'Знание'
        SKILL = 'SKILL', 'Умение'
        ACTION = 'ACT', 'Трудовое действие'
    
    labor_function = models.ForeignKey(LaborFunction, on_delete=models.CASCADE, related_name='details')
    type = models.CharField(max_length=10, choices=DetailType.choices)
    code = models.CharField(max_length=20)
    name = models.TextField()
    def __str__(self):
        return f"[{self.get_type_display()}] {self.name[:50]}"
    class Meta:
        verbose_name = "Деталь функции"
        verbose_name_plural = "Знания, умения, действия"

class Post(models.Model):

    name = models.TextField()
    code = models.CharField(max_length=50, blank=True, null=True, verbose_name="Код ОКПДТР")
    generalized_functions = models.ManyToManyField(
        GeneralizedLaborFunction, 
        blank=True, 
        verbose_name="Связанные ОТФ"
    )

    def __str__(self):
        prefix = f"[{self.code}] " if self.code else ""
        return f"{prefix}{self.name[:100]}"

    class Meta:
        verbose_name = "Должность"
        verbose_name_plural = "Должности"

class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255)
    post = models.ForeignKey(Post, on_delete=models.PROTECT)
    is_admin = models.BooleanField(default=False)
    external_id = models.CharField(max_length=50, unique=True)
    
    
    skills = models.ManyToManyField(
        LaborFunctionDetails, 
        through='EmployeeSkillProgress',
        related_name='employees'
    )
    def __str__(self):
        return self.name
    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        if self.post:
            self.sync_skills()

    def sync_skills(self):
        from .models import LaborFunctionDetails, EmployeeSkillProgress
        
        otfs = self.post.generalized_functions.all()

        details = LaborFunctionDetails.objects.filter(
            labor_function__generalized_function__in=otfs
        ).distinct()

        with transaction.atomic():
            for detail in details:
                EmployeeSkillProgress.objects.get_or_create(
                    employee=self,
                    skill_detail=detail,
                    defaults={'level': 0.0}
                )
    def is_busy(self):
        return self.task_set.filter(status='in_progress').exists()

class EmployeeSkillProgress(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    skill_detail = models.ForeignKey(LaborFunctionDetails, on_delete=models.CASCADE)
    level = models.FloatField(default=0.0) # уровень освоения
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Прогресс навыка"
        verbose_name_plural = "Прогресс навыков"
        unique_together = ('employee', 'skill_detail')
        

class Project(models.Model):
    name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=100)
    manager = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True)
    def __str__(self):
        return self.name
    class Meta:
        verbose_name = "Проект"
        verbose_name_plural = "Проекты"

class Task(models.Model):
    class Status(models.TextChoices):
            TODO = 'todo', 'Нужно сделать'
            IN_PROGRESS = 'in_progress', 'В работе'
            TO_CONFIRM = 'to_confirm', 'Нужно подтвердить'
            COMPLETED = 'completed', 'Завершена'
    class Grade(models.TextChoices):
        EXCELLENT = 'excellent', 'Отлично'
        GOOD = 'good', 'Хорошо'
        REWORK = 'rework', 'На переделку'
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    executor = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=255)
    description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    required_skills = models.ManyToManyField(LaborFunctionDetails, related_name='tasks')
    grade = models.CharField(
        max_length=20, 
        choices=Grade.choices, 
        null=True, 
        blank=True, 
        verbose_name="Оценка руководителя"
    )
    def __str__(self):
        return self.name
    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"

class SkillLog(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    skill_detail = models.ForeignKey(LaborFunctionDetails, on_delete=models.CASCADE)
    level_reached = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=255)
    class Meta:
        verbose_name = "Лог навыка"
        verbose_name_plural = "История изменений навыков"

class ParserSettings(models.Model):
    folder_path = models.CharField(max_length=500, verbose_name="Путь к папке с XML")
    last_update = models.DateTimeField(auto_now=True, verbose_name="Дата последнего обновления")

    class Meta:
        verbose_name = "Настройки парсера"
        verbose_name_plural = "Настройки парсера"

    def __str__(self):
        return self.folder_path

class Notification(models.Model):
    recipient = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ['-created_at']

    def __str__(self):
        return f"Для {self.recipient.name}: {self.message[:30]}"