from django.apps import AppConfig


class QualificationappConfig(AppConfig):
    name = 'QualificationApp'
    def ready(self):
        import QualificationApp.signals
