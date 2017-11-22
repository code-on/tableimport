from django.contrib.auth.models import User
from django.db import models


class Example(models.Model):
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
