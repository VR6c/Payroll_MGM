from django.db import models

class Company(models.Model):
    name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    def __str__(self):
        return self.name

class Department(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Position(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='positions')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='positions')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        ordering = ['name']

    def __str__(self):
        if self.department:
            return f"{self.name} ({self.department.name})"
        return self.name


class Branch(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, blank=True, help_text="e.g. F1, F2, HQ")
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name