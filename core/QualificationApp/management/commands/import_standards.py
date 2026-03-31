from django.core.management.base import BaseCommand
from QualificationApp.services import ProfStandartParser
import os

class Command(BaseCommand):
    help = 'Загружает профстандарты из XML файла в базу данных'

    def handle(self, *args, **options):
        file_path = 'ProfessionalStandarts_1223.xml'
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'Файл {file_path} не найден!'))
            return

        self.stdout.write(self.style.SUCCESS('Начинаю парсинг...'))
        
        parser = ProfStandartParser(file_path)
        parser.run()

        self.stdout.write(self.style.SUCCESS('Данные успешно загружены в БД!'))