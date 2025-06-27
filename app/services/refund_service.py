from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from ..models.models import TPointsTransaction, Order
from ..core.base import BaseService
from ..core.constants import TransactionType
from ..repositories.billing_repository import BillingRepository

logger = logging.getLogger(__name__)

class RefundService(BaseService):
    """Сервис для обработки возвратов T-Points"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.billing_repo = BillingRepository(session)
    
    async def process_order_refund(self, order_id: int, user_id: int, refund_amount: float) -> bool:
        """
        Обработать возврат средств за отмененный заказ
        ИСПРАВЛЕНО: только создание транзакции через репозиторий
        """
        try:
            # Создаем объект транзакции возврата
            refund_transaction = TPointsTransaction(
                user_id=user_id,
                order_id=order_id,
                points_amount=int(refund_amount),
                description=f"Возврат средств за отмененный заказ #{order_id}",
                transaction_type=TransactionType.REFUND
            )
            
            # Получаем текущий баланс пользователя
            current_balance = await self.billing_repo.get_user_balance(user_id)
            if current_balance is None:
                logger.error(f"User {user_id} not found for refund")
                return False
            
            new_balance = current_balance + int(refund_amount)
            
            # Атомарно создаем транзакцию и обновляем баланс
            created_transaction = await self.billing_repo.create_transaction_with_balance_update(
                refund_transaction, new_balance
            )
            
            if created_transaction:
                logger.info(f"Refunded {refund_amount} T-Points to user {user_id} for cancelled order {order_id}")
                return True
            else:
                logger.error(f"Failed to create refund transaction for order {order_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing refund for order {order_id}: {e}")
            return False
    
    async def get_refund_transactions(self, order_id: int) -> list:
        """Получить все транзакции возврата по заказу"""
        try:
            transactions = await self.billing_repo.get_transactions_by_order(order_id)
            refund_transactions = [
                t for t in transactions 
                if t.transaction_type == TransactionType.REFUND
            ]
            return refund_transactions
        except Exception as e:
            logger.error(f"Error getting refund transactions for order {order_id}: {e}")
            return [] 