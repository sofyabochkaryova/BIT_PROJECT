"""
Удаление дублей актов и счетов по заявкам.
Оставляет по одному последнему (новому) акту и счету на заявку.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Max
from documents.models import BusinessDocument


class Command(BaseCommand):
    help = 'Удалить дубликаты актов и счетов по заявкам. Оставляет по одному новому документу каждого типа.'

    def handle(self, *args, **options):
        """Основная логика удаления дубликатов."""
        self.stdout.write(self.style.SUCCESS('Поиск дубликатов актов и счетов...'))
        
        # Найдём заявки с несколькими актами
        acts_to_delete = []
        invoices_to_delete = []
        
        # Процесс для актов
        act_duplicates = BusinessDocument.objects.filter(doc_type='act').values('request').annotate(
            count=Count('id'),
            max_id=Max('id')
        ).filter(count__gt=1)
        
        for dup in act_duplicates:
            request_id = dup['request']
            keep_id = dup['max_id']
            # Удаляем все кроме самого нового
            acts_to_delete.extend(
                BusinessDocument.objects.filter(
                    request_id=request_id,
                    doc_type='act'
                ).exclude(id=keep_id).values_list('id', flat=True)
            )
        
        # Процесс для счетов
        invoice_duplicates = BusinessDocument.objects.filter(doc_type='invoice').values('request').annotate(
            count=Count('id'),
            max_id=Max('id')
        ).filter(count__gt=1)
        
        for dup in invoice_duplicates:
            request_id = dup['request']
            keep_id = dup['max_id']
            # Удаляем все кроме самого нового
            invoices_to_delete.extend(
                BusinessDocument.objects.filter(
                    request_id=request_id,
                    doc_type='invoice'
                ).exclude(id=keep_id).values_list('id', flat=True)
            )
        
        total_to_delete = len(acts_to_delete) + len(invoices_to_delete)
        
        if not total_to_delete:
            self.stdout.write(self.style.SUCCESS('✓ Дубликатов не найдено.'))
            return
        
        self.stdout.write(
            self.style.WARNING(f'Найдено дубликатов: {len(acts_to_delete)} актов, {len(invoices_to_delete)} счетов')
        )
        
        # Удаляем дубликаты
        if acts_to_delete:
            deleted_count, _ = BusinessDocument.objects.filter(id__in=acts_to_delete).delete()
            self.stdout.write(self.style.SUCCESS(f'✓ Удалено актов: {deleted_count}'))
        
        if invoices_to_delete:
            deleted_count, _ = BusinessDocument.objects.filter(id__in=invoices_to_delete).delete()
            self.stdout.write(self.style.SUCCESS(f'✓ Удалено счетов: {deleted_count}'))
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Завершено! Удалено всего документов: {total_to_delete}')
        )
