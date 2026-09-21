from django.db import models
from django.conf import settings

class Activity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    employee = models.ForeignKey('employees.Employee', on_delete=models.SET_NULL, null=True, blank=True)
    module = models.CharField(max_length=50)
    action = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Activities'
        indexes = [models.Index(fields=['-created_at']), models.Index(fields=['module', 'action'])]

    def __str__(self):
        return f"{self.user} | {self.action} | {self.created_at}"
