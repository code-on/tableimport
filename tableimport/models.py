from django.db import models
from django.utils import timezone

from django.conf import settings


class Upload(models.Model):
    file = models.FileField(upload_to='uploads/%y/%m/%d/')
    user = models.ForeignKey(settings.AUTH_USER_MODEL)

    def file_name(self):
        return self.file.name.split('/')[-1]

class Column(models.Model):
    upload = models.ForeignKey(Upload)
    col_num = models.SmallIntegerField()
    field = models.CharField(max_length=100)

    class Meta:
        unique_together = [['upload', 'col_num'], ['upload', 'field']]


class ColumnUploadError(models.Model):
    upload = models.ForeignKey(Upload)
    row_num = models.PositiveIntegerField()
    row = models.FileField(upload_to='json_row/')
    errors = models.FileField(upload_to='json_errors/')

    class Meta:
        ordering =['row_num']
