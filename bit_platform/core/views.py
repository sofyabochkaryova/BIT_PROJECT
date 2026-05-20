from datetime import datetime

from django.shortcuts import render


def home_view(request):
	context = {
		'services_count': 13,
		'projects_completed': 120,
		'happy_clients': 87,
		'support_hours': 2500,
		'current_year': datetime.now().year,
	}
	return render(request, 'core/home.html', context)


def dashboard_view(request):
	context = {
		'current_year': datetime.now().year,
		'open_requests': 32,
		'active_projects': 14,
		'conversion_rate': 68,
		'revenue': '2 968 050 ₽',
		'pipeline': [58, 82, 45, 76, 90, 64, 71],
		'team_load': [
			{'name': 'Аналитика', 'value': 78},
			{'name': 'Разработка', 'value': 91},
			{'name': 'Тестирование', 'value': 66},
			{'name': 'Поддержка', 'value': 54},
		],
	}
	return render(request, 'core/dashboard.html', context)


def privacy_view(request):
	context = {'current_year': datetime.now().year}
	return render(request, 'core/privacy.html', context)


def terms_view(request):
	context = {'current_year': datetime.now().year}
	return render(request, 'core/terms.html', context)
