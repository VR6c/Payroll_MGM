from companies.models import Company

def get_default_company():
    """
    Retrieves the primary active company, or creates a default company if none exists.
    """
    comp = Company.objects.filter(status=True).first() or Company.objects.first()
    if not comp:
        comp = Company.objects.create(name="Payroll MGM Co., Ltd.", status=True)
    return comp
