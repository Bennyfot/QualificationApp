from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Task, Notification

@receiver(post_save, sender=Task)
def notify_executor_assigned(sender, instance, created, **kwargs):
    # Уведомляем только если исполнитель указан
    if instance.executor:
        Notification.objects.create(
            recipient=instance.executor,
            message=f"Вы назначены исполнителем новой задачи: {instance.name} (Проект: {instance.project.name})"
        )