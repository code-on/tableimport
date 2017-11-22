import os
from django import forms
from .models import Upload


class UploadForm(forms.ModelForm):
    ALLOWED_FORMATS = ['.xls', '.xlsx']

    class Meta:
        model = Upload
        fields = ['file']

    def clean_file_excel(self):
        excel = self.cleaned_data['file_excel']
        extension = os.path.splitext(excel.name)[1]
        if not extension in self.ALLOWED_FORMATS:
            self.add_error('file_excel', 'allowed formats are: %s'.format(unicode(self.ALLOWED_FORMATS)))
            raise forms.ValidationError('not allowed format')
        return excel
