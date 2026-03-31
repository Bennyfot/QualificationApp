from django import forms

class XMLUploadForm(forms.Form):
    xml_file = forms.FileField(label="Выберите XML файл профстандарта")