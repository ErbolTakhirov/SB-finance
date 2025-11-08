"""
Сигналы Django для автоматического обновления финансовой памяти
после создания/обновления/удаления транзакций.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Income, Expense
from .utils.analytics import update_user_financial_memory


@receiver(post_save, sender=Income)
@receiver(post_save, sender=Expense)
@receiver(post_delete, sender=Income)
@receiver(post_delete, sender=Expense)
def update_financial_memory_on_transaction_change(sender, instance, **kwargs):
    """Обновляет финансовую память пользователя после изменения транзакций."""
    if instance.user:
        try:
            # Обновляем память принудительно
            update_user_financial_memory(instance.user, force_refresh=True)
        except Exception:
            # Игнорируем ошибки, чтобы не блокировать сохранение транзакции
            pass

