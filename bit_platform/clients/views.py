from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import ClientCompany


@login_required
def my_company(request):
    """Просмотр / редактирование реквизитов компании клиента."""
    company = ClientCompany.objects.filter(owner=request.user).first()

    if request.method == 'POST':
        data = request.POST
        files = request.FILES

        if company is None:
            company = ClientCompany(owner=request.user)

        company.short_name = data.get('short_name', '').strip()
        company.full_name = data.get('full_name', '').strip()
        company.legal_form = data.get('legal_form', 'ooo')
        company.inn = data.get('inn', '').strip()
        company.kpp = data.get('kpp', '').strip()
        company.ogrn = data.get('ogrn', '').strip()
        company.legal_address = data.get('legal_address', '').strip()
        company.actual_address = data.get('actual_address', '').strip()
        company.bank_name = data.get('bank_name', '').strip()
        company.bik = data.get('bik', '').strip()
        company.corr_account = data.get('corr_account', '').strip()
        company.settlement_account = data.get('settlement_account', '').strip()
        company.director_name = data.get('director_name', '').strip()
        company.director_position = data.get('director_position', 'Генеральный директор').strip()
        company.director_basis = data.get('director_basis', 'Устава').strip()
        company.phone = data.get('phone', '').strip()
        company.email = data.get('email', '').strip()
        company.website = data.get('website', '').strip()

        if 'stamp_image' in files:
            company.stamp_image = files['stamp_image']
        if 'signature_image' in files:
            company.signature_image = files['signature_image']

        company.save()
        messages.success(request, 'Реквизиты компании сохранены')
        return redirect('clients:my_company')

    return render(request, 'clients/my_company.html', {
        'company': company,
        'form_choices': ClientCompany.FORM_CHOICES,
    })
