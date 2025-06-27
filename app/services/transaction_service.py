from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.models.models import TPointsTransaction, User, Product, TPointsActivity
from app.core.base import BaseService
from app.core.constants import TransactionType
from app.repositories.billing_repository import BillingRepository

logger = logging.getLogger(__name__)

class TransactionService(BaseService):
    """
    Сервис для работы с транзакциями T-Points
    ИСПРАВЛЕНО: работает через репозиторий, содержит только бизнес-логику
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.billing_repo = BillingRepository(session)

    async def create_transaction(
        self,
        user_id: int,
        amount: int,
        description: str,
        product_id: Optional[int] = None,
        activity_id: Optional[int] = None,
        transaction_type: str = TransactionType.TOP_UP,
        order_id: Optional[int] = None
    ) -> Optional[TPointsTransaction]:
        """
        Создать новую транзакцию T-Points
        ИСПРАВЛЕНО: атомарная операция через репозиторий + поддержка типов
        """
        try:
            # Бизнес-логика: валидация данных
            if amount == 0:
                logger.error(f"Invalid amount: {amount}")
                return None
            
            # Получаем пользователя через репозиторий
            user = await self.billing_repo.get_user_by_id(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return None
            
            # Бизнес-логика: проверка баланса для списания
            if amount < 0 and user.tpoints < abs(amount):
                logger.warning(f"Insufficient T-points for user {user_id}: {user.tpoints} < {abs(amount)}")
                return None
            
            # Создаем объект транзакции
            transaction = TPointsTransaction(
                user_id=user_id,
                product_id=product_id,
                activity_id=activity_id,
                order_id=order_id,
                points_amount=amount,
                description=description,
                transaction_type=transaction_type
            )
            
            # Вычисляем новый баланс
            new_balance = user.tpoints + amount
            
            # Атомарно создаем транзакцию и обновляем баланс
            created_transaction = await self.billing_repo.create_transaction_with_balance_update(
                transaction, new_balance
            )
            
            if created_transaction:
                logger.info(f"Transaction created: ID {created_transaction.id}, User {user_id}, Amount {amount}, Type {transaction_type}")
            
            return created_transaction
            
        except Exception as e:
            logger.error(f"Error creating transaction for user {user_id}: {e}")
            return None

    async def get_user_transactions(self, user_id: int, limit: int = 100) -> List[TPointsTransaction]:
        """
        Получить историю транзакций пользователя
        ИСПРАВЛЕНО: работа через репозиторий
        """
        try:
            transactions = await self.billing_repo.get_user_transactions(user_id, limit)
            logger.info(f"Retrieved {len(transactions)} transactions for user {user_id}")
            return transactions
        except Exception as e:
            logger.error(f"Error retrieving transactions for user {user_id}: {e}")
            return []

    async def get_user_balance(self, user_id: int) -> int:
        """
        Получить текущий баланс T-Points пользователя
        ИСПРАВЛЕНО: работа через репозиторий
        """
        try:
            user = await self.billing_repo.get_user_by_id(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return 0
            
            balance = user.tpoints
            logger.info(f"Balance for user {user_id}: {balance}")
            return balance
        except Exception as e:
            logger.error(f"Error retrieving balance for user {user_id}: {e}")
            return 0

    async def get_transaction_by_id(self, transaction_id: int) -> Optional[TPointsTransaction]:
        """
        Получить транзакцию по ID
        ИСПРАВЛЕНО: работа через репозиторий
        """
        try:
            transaction = await self.billing_repo.get_transaction_by_id(transaction_id)
            
            if transaction is None:
                logger.warning(f"Transaction {transaction_id} not found")
            else:
                logger.info(f"Retrieved transaction {transaction_id}")
            
            return transaction
        except Exception as e:
            logger.error(f"Error retrieving transaction {transaction_id}: {e}")
            return None
    
    async def add_points(self, user_id: int, points: int, description: str, activity_id: Optional[int] = None) -> bool:
        """
        Добавить T-Points пользователю с созданием транзакции
        """
        try:
            if points <= 0:
                logger.error(f"Invalid points amount for adding: {points}")
                return False
            
            if not description or description.strip() == "":
                logger.error(f"Description is required for adding points")
                return False
            
            transaction = await self.create_transaction(
                user_id=user_id,
                amount=points,
                description=description.strip(),
                activity_id=activity_id,
                transaction_type=TransactionType.TOP_UP
            )
            
            success = transaction is not None
            if success:
                logger.info(f"Successfully added {points} points to user {user_id}")
            else:
                logger.error(f"Failed to add {points} points to user {user_id}")
            
            return success
        except Exception as e:
            logger.error(f"Error adding points to user {user_id}: {e}")
            return False
    
    async def remove_points(self, user_id: int, points: int, description: str) -> bool:
        """
        Списать T-Points у пользователя с созданием транзакции
        """
        try:
            if points <= 0:
                logger.error(f"Invalid points amount for removal: {points}")
                return False
            
            if not description or description.strip() == "":
                logger.error(f"Description is required for removing points")
                return False
            
            # Дополнительная проверка баланса перед списанием
            current_balance = await self.get_user_balance(user_id)
            if current_balance < points:
                logger.warning(f"Insufficient balance for user {user_id}: {current_balance} < {points}")
                return False
            
            # Создаем транзакцию с отрицательным amount
            transaction = await self.create_transaction(
                user_id=user_id,
                amount=-points,  # Отрицательное значение для списания
                description=description.strip(),
                transaction_type=TransactionType.DEBIT
            )
            
            success = transaction is not None
            if success:
                logger.info(f"Successfully removed {points} points from user {user_id}")
            else:
                logger.error(f"Failed to remove {points} points from user {user_id}")
            
            return success
        except Exception as e:
            logger.error(f"Error removing points from user {user_id}: {e}")
            return False

    async def bulk_points_operation(self, operations: List[dict]) -> dict:
        """
        Массовая операция с T-Points
        operations: [{"user_id": int, "points": int, "description": str, "operation": "add"|"remove"}]
        Возвращает: {"success": int, "failed": int, "errors": []}
        """
        result = {"success": 0, "failed": 0, "errors": []}
        
        for i, operation in enumerate(operations):
            try:
                user_id = operation.get("user_id")
                points = operation.get("points")
                description = operation.get("description")
                op_type = operation.get("operation")
                
                if not all([user_id, points, description, op_type]):
                    result["failed"] += 1
                    result["errors"].append(f"Строка {i+1}: Отсутствуют обязательные поля")
                    continue
                
                if op_type == "add":
                    success = await self.add_points(user_id, points, description)
                elif op_type == "remove":
                    success = await self.remove_points(user_id, points, description)
                else:
                    result["failed"] += 1
                    result["errors"].append(f"Строка {i+1}: Неизвестная операция '{op_type}'")
                    continue
                
                if success:
                    result["success"] += 1
                else:
                    result["failed"] += 1
                    result["errors"].append(f"Строка {i+1}: Ошибка выполнения операции для пользователя {user_id}")
                    
            except Exception as e:
                result["failed"] += 1
                result["errors"].append(f"Строка {i+1}: {str(e)}")
        
        logger.info(f"Bulk operation completed: {result['success']} success, {result['failed']} failed")
        return result 

    async def get_transactions_journal(self, limit: int = 50, user_id: Optional[int] = None) -> List[dict]:
        """
        Получить журнал операций T-Points
        """
        try:
            if user_id:
                transactions = await self.get_user_transactions(user_id, limit)
            else:
                # Получаем последние транзакции всех пользователей
                transactions = await self.billing_repo.get_recent_transactions(limit)
            
            journal = []
            for transaction in transactions:
                try:
                    # Получаем данные пользователя
                    user = await self.billing_repo.get_user_by_id(transaction.user_id)
                    
                    journal_entry = {
                        'id': transaction.id,
                        'user_id': transaction.user_id,
                        'user_fullname': user.fullname if user else 'Неизвестный пользователь',
                        'user_username': user.username if user else None,
                        'points_amount': transaction.points_amount,
                        'description': transaction.description,
                        'created_at': transaction.created_at,
                        'type': 'начисление' if transaction.points_amount > 0 else 'списание',
                        'transaction_type': transaction.transaction_type,
                        'transaction_type_name': TransactionType.get_display_name(transaction.transaction_type),
                        'order_id': transaction.order_id,
                        'activity': None,
                        'product': None
                    }
                    
                    # Добавляем информацию об активности, если есть
                    if transaction.activity_id and hasattr(transaction, 'activity') and transaction.activity:
                        journal_entry['activity'] = {
                            'id': transaction.activity.id,
                            'name': transaction.activity.name,
                            'points': transaction.activity.points
                        }
                    
                    # Добавляем информацию о продукте, если есть
                    if transaction.product_id and hasattr(transaction, 'product') and transaction.product:
                        journal_entry['product'] = {
                            'id': transaction.product.id,
                            'name': transaction.product.name,
                            'price': transaction.product.price
                        }
                    
                    journal.append(journal_entry)
                    
                except Exception as e:
                    logger.error(f"Error processing transaction {transaction.id} for journal: {e}")
                    continue
            
            logger.info(f"Generated journal with {len(journal)} entries")
            return journal
            
        except Exception as e:
            logger.error(f"Error generating transactions journal: {e}")
            return []

    async def get_tpoints_stats(self) -> dict:
        """Получить статистику по T-Points"""
        try:
            stats = await self.billing_repo.get_tpoints_stats()
            return {
                'total_points': stats.get('total_points', 0),
                'active_users': stats.get('active_users', 0),
                'monthly_transactions': stats.get('monthly_transactions', 0)
            }
        except Exception as e:
            logger.error(f"Error getting T-Points stats: {e}")
            return {
                'total_points': 0,
                'active_users': 0,
                'monthly_transactions': 0
            }

    # ===================== МЕТОДЫ ДЛЯ РАБОТЫ С ЗАКАЗАМИ =====================
    
    async def create_purchase_transaction(
        self,
        user_id: int,
        order_id: int,
        amount: int,
        description: Optional[str] = None
    ) -> Optional[TPointsTransaction]:
        """
        Создать транзакцию покупки для заказа
        amount должен быть отрицательным (списание)
        """
        try:
            if amount >= 0:
                logger.error(f"Purchase amount must be negative, got: {amount}")
                return None
            
            if not description:
                description = f"Оплата заказа №{order_id}"
            
            return await self.create_transaction(
                user_id=user_id,
                amount=amount,
                description=description,
                transaction_type=TransactionType.PURCHASE,
                order_id=order_id
            )
        except Exception as e:
            logger.error(f"Error creating purchase transaction: {e}")
            return None
    
    async def create_refund_transaction(
        self,
        user_id: int,
        order_id: int,
        amount: int,
        description: Optional[str] = None
    ) -> Optional[TPointsTransaction]:
        """
        Создать транзакцию возврата за отмененный заказ
        amount должен быть положительным (возврат)
        """
        try:
            if amount <= 0:
                logger.error(f"Refund amount must be positive, got: {amount}")
                return None
            
            if not description:
                description = f"Возврат за отмененный заказ №{order_id}"
            
            return await self.create_transaction(
                user_id=user_id,
                amount=amount,
                description=description,
                transaction_type=TransactionType.REFUND,
                order_id=order_id
            )
        except Exception as e:
            logger.error(f"Error creating refund transaction: {e}")
            return None
    
    async def create_activity_transaction(
        self,
        user_id: int,
        activity_id: int,
        points: int,
        description: Optional[str] = None
    ) -> Optional[TPointsTransaction]:
        """
        Создать транзакцию за выполнение активности
        """
        try:
            if points <= 0:
                logger.error(f"Activity points must be positive, got: {points}")
                return None
            
            if not description:
                # Получаем название активности
                activity = await self.billing_repo.get_activity_by_id(activity_id) 
                activity_name = activity.name if activity else "активность"
                description = f"Начисление за: {activity_name}"
            
            return await self.create_transaction(
                user_id=user_id,
                amount=points,
                description=description,
                transaction_type=TransactionType.EARNING,
                activity_id=activity_id
            )
        except Exception as e:
            logger.error(f"Error creating activity transaction: {e}")
            return None
    
    async def get_order_transactions(self, order_id: int) -> List[TPointsTransaction]:
        """
        Получить все транзакции связанные с заказом
        """
        try:
            return await self.billing_repo.get_transactions_by_order(order_id)
        except Exception as e:
            logger.error(f"Error getting transactions for order {order_id}: {e}")
            return []
    
    async def get_transaction_summary_by_type(self, user_id: Optional[int] = None) -> dict:
        """
        Получить сводку транзакций по типам
        """
        try:
            transactions = await self.billing_repo.get_user_transactions(user_id, 1000) if user_id else await self.billing_repo.get_recent_transactions(1000)
            
            summary = {}
            for transaction in transactions:
                t_type = transaction.transaction_type
                type_name = TransactionType.get_display_name(t_type)
                
                if type_name not in summary:
                    summary[type_name] = {
                        'count': 0,
                        'total_amount': 0,
                        'type_code': t_type
                    }
                
                summary[type_name]['count'] += 1
                summary[type_name]['total_amount'] += transaction.points_amount
            
            return summary
        except Exception as e:
            logger.error(f"Error getting transaction summary: {e}")
            return {} 