import xml.etree.ElementTree as ET
from datetime import datetime
from django.db import transaction
import re
import os
from .models import (
    Profession, GeneralizedLaborFunction, LaborFunction, 
    LaborFunctionDetails, Post,
    Employee, Project, Task
)

class ProfStandartParser:
    def __init__(self, xml_file_path):
        self.xml_path = xml_file_path

    def run(self):
        try:
            with open(self.xml_path, 'r', encoding='utf-8') as f:
                xml_string = f.read()
            
            if not xml_string.strip():
                return 'error'

            # Очистка пространств имен
            xml_string = re.sub(r'\sxmlns="[^"]+"', '', xml_string, count=1)
            xml_string = re.sub(r'\sxmlns:xsi="[^"]+"', '', xml_string, count=1)
            xml_string = re.sub(r'\sxmlns:xsd="[^"]+"', '', xml_string, count=1)

            root = ET.fromstring(xml_string)
            stand = root.find('.//ProfessionalStandart')

            if stand is None:
                return 'error'

            # Проверка на дубликаты по регистрационному номеру
            reg_number = stand.find('RegistrationNumber').text.strip()
            if Profession.objects.filter(code=reg_number).exists():
                return 'exists'

            # Начало транзакции для сохранения данных
            with transaction.atomic():
                name_prof = stand.find('NameProfessionalStandart').text.strip()
                date_str = stand.find('DateOfApproval').text.strip()
                try:
                    publish_date = datetime.strptime(date_str, '%d.%m.%Y').date()
                except:
                    publish_date = datetime.now().date()

                prof_obj = Profession.objects.create(
                    code=reg_number,
                    name=name_prof,
                    publish_date=publish_date
                )

                # Парсинг ОТФ
                otfs = stand.findall('.//GeneralizedWorkFunctions/GeneralizedWorkFunction')
                for otf_xml in otfs:
                    otf_code = otf_xml.find('CodeOTF').text.strip()
                    otf_name = otf_xml.find('NameOTF').text.strip()
                    
                    otf_obj, _ = GeneralizedLaborFunction.objects.get_or_create(
                        profession=prof_obj,
                        code=otf_code,
                        defaults={'name': otf_name}
                    )

                    # Должности из OtherCharacteristicPlus/ListOKPDTR
                    other_char_plus = otf_xml.find('.//OtherCharacteristicPlus')
                    if other_char_plus is not None:
                        okpdtr_units = other_char_plus.findall('.//ListOKPDTR/UnitOKPDTR')
                        for unit in okpdtr_units:
                            name_el = unit.find('NameOKPDTR')
                            code_el = unit.find('CodeOKPDTR')

                            if name_el is not None and name_el.text:
                                job_name = name_el.text.strip()
                                job_code = code_el.text.strip() if code_el is not None and code_el.text else ""

                                post_obj, _ = Post.objects.get_or_create(
                                    name=job_name,
                                    code=job_code
                                )
                                post_obj.generalized_functions.add(otf_obj)

                    # Парсинг ТФ
                    tfs = otf_xml.findall('.//ParticularWorkFunctions/ParticularWorkFunction')
                    for tf_xml in tfs:
                        tf_code = tf_xml.find('CodeTF').text.strip()
                        tf_name = tf_xml.find('NameTF').text.strip()

                        lf_obj, _ = LaborFunction.objects.get_or_create(
                            generalized_function=otf_obj,
                            code=tf_code,
                            defaults={'name': tf_name}
                        )

                        # Парсинг трудовых действий
                        labor_actions = tf_xml.findall('.//LaborActions/LaborAction')
                        for idx, action in enumerate(labor_actions):
                            if action.text and action.text.strip():
                                LaborFunctionDetails.objects.get_or_create(
                                    labor_function=lf_obj,
                                    name=action.text.strip(),
                                    type=LaborFunctionDetails.DetailType.ACTION,
                                    defaults={'code': f"{tf_code}.A.{idx+1}"}
                                )

                        # Парсинг умений
                        skills_section = tf_xml.find('.//RequiredSkills')
                        if skills_section is not None:
                            skills = skills_section.findall('.//RequiredSkill')
                            for idx, s in enumerate(skills):
                                if s.text and s.text.strip():
                                    LaborFunctionDetails.objects.get_or_create(
                                        labor_function=lf_obj,
                                        name=s.text.strip(),
                                        type=LaborFunctionDetails.DetailType.SKILL,
                                        defaults={'code': f"{tf_code}.S.{idx+1}"}
                                    )

                        # Парсинг знаний
                        knows_section = tf_xml.find('.//NecessaryKnowledges')
                        if knows_section is not None:
                            knows = knows_section.findall('.//NecessaryKnowledge')
                            for idx, k in enumerate(knows):
                                if k.text and k.text.strip():
                                    LaborFunctionDetails.objects.get_or_create(
                                        labor_function=lf_obj,
                                        name=k.text.strip(),
                                        type=LaborFunctionDetails.DetailType.KNOWLEDGE,
                                        defaults={'code': f"{tf_code}.K.{idx+1}"}
                                    )

            return 'created'

        except Exception as e:
            print(f"Ошибка при парсинге {self.xml_path}: {e}")
            import traceback
            traceback.print_exc()
            return 'error'
            
class EmployeeParser:
    def __init__(self, xml_file_path):
        self.xml_path = xml_file_path

    def run(self):
        try:
            tree = ET.parse(self.xml_path)
            root = tree.getroot()

            created_count = 0
            with transaction.atomic():
                for emp_xml in root.findall('.//Employee'):
                    full_name = emp_xml.find('FullName').text.strip()
                    internal_number = emp_xml.find('InternalNumber').text.strip()
                    okpdtr_code = emp_xml.find('OKPDTR').text.strip()

                    # Ищем должность по коду ОКПДТР
                    post = Post.objects.filter(code__startswith=okpdtr_code[:5]).first()

                    if not post:
                        print(f"Предупреждение: Должность с кодом {okpdtr_code} не найдена для {full_name}")
                        continue

                    # Создаем или обновляем сотрудника
                    employee, created = Employee.objects.update_or_create(
                        external_id=internal_number, 
                        defaults={
                            'name': full_name,
                            'post': post
                        }
                    )
                    if created:
                        created_count += 1

            return f"Processed. Created: {created_count}"
        except Exception as e:
            print(f"Ошибка парсинга сотрудников: {e}")
            return 'error'


class ProjectTaskParser:
    """Парсер проектов и задач из XML"""
    def __init__(self, xml_file_path):
        self.xml_path = xml_file_path

    def run(self):
        try:
            tree = ET.parse(self.xml_path)
            root = tree.getroot()

            with transaction.atomic():
                for proj_xml in root.findall('.//Project'):
                    # Извлекаем данные проекта
                    p_id = proj_xml.find('ProjectID').text.strip()
                    p_title = proj_xml.find('ProjectTitle').text.strip()
                    p_start = proj_xml.find('ProjectStartDate').text.strip()
                    
                    p_end_node = proj_xml.find('ProjectEndDate')
                    p_end = p_end_node.text.strip() if p_end_node is not None and p_end_node.text else None

                    # Поиск менеджера
                    manager_node = proj_xml.find('ManagerInternalNumber')
                    manager_obj = None
                    if manager_node is not None and manager_node.text:
                        internal_number = manager_node.text.strip()
                        manager_obj = Employee.objects.filter(external_id=internal_number).first()

                    # Синхронизируем проект
                    project, _ = Project.objects.update_or_create(
                        name=p_title, 
                        defaults={
                            'start_date': p_start,
                            'end_date': p_end,
                            'manager': manager_obj,
                            'status': 'active'
                        }
                    )

                    # Парсим задачи проекта
                    tasks = proj_xml.findall('.//Tasks/Task')
                    for task_xml in tasks:
                        t_title = task_xml.find('TaskTitle').text.strip()
                        t_desc = task_xml.find('TaskDescription')
                        t_start = task_xml.find('TaskStartDate').text.strip()
                        
                        t_end_node = task_xml.find('TaskEndDate')
                        t_end = t_end_node.text.strip() if t_end_node is not None and t_end_node.text else None

                        # Синхронизируем задачу
                        Task.objects.update_or_create(
                            project=project,
                            name=t_title,
                            defaults={
                                'description': t_desc.text.strip() if t_desc is not None else "",
                                'start_date': t_start,
                                'end_date': t_end,
                                'status': Task.Status.TODO
                            }
                        )

            return "Projects and tasks synchronized"
        except Exception as e:
            print(f"Ошибка парсинга проектов: {e}")
            return 'error'