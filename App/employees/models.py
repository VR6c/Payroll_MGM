from django.db import models
from django.conf import settings
from django.utils import timezone
from companies.models import Company, Department, Position

class ActiveEmployeeManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True, anonymized=False)

class Employee(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        RESIGNED = 'resigned', 'Resigned'
        TERMINATED = 'terminated', 'Terminated'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='employee_profile')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='employees')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, blank=True)
    manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subordinates')
    employee_code = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=[('M','Male'),('F','Female'),('O','Other')])
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(unique=True)
    address = models.TextField(blank=True)
    photo = models.ImageField(upload_to='employee_photos/', null=True, blank=True)
    join_date = models.DateField()
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    deleted_at = models.DateTimeField(null=True, blank=True)
    anonymized = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveEmployeeManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['first_name', 'last_name']
        indexes = [models.Index(fields=['company', 'status']), models.Index(fields=['deleted_at'])]

    def __str__(self):
        return f"{self.employee_code} - {self.first_name} {self.last_name}"

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.status = 'terminated'
        self.save(update_fields=['deleted_at', 'status'])

    def anonymize(self):
        self.first_name = '[REDACTED]'
        self.last_name = '[REDACTED]'
        self.email = f'redacted_{self.pk}@deleted.local'
        self.phone = ''
        self.address = ''
        if self.photo:
            self.photo.delete(save=False)
        self.anonymized = True
        self.save()
