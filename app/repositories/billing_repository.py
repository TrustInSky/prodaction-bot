"""
Репозиторий для работы с транзакциями T-Points
Содержит ВСЮ работу с БД для биллинга
"""
from typing import List, Optional
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from ..models.models import TPointsTransaction, User, TPointsActivity
from ..core.base import BaseRepository
import logging

logger = logging.getLogger(__name__)

class BillingRepository(BaseRepository):
    """Репозиторий для всех операций с транзакциями и балансом"""

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по telegram_id (primary key)"""
        try:
            # user_id в нашей системе это telegram_id (primary key)
            query = select(User).where(User.telegram_id == user_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None

    async def get_user_by_id_for_update(self, user_id: int) -> Optional[User]:
        """
        Получить пользователя с блокировкой для обновления
        Для предотвращения race conditions при конкурентных операциях
        """
        try:
            query = select(User).where(User.telegram_id == user_id).with_for_update()
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting user for update {user_id}: {e}")
            return None

    async def create_transaction(self, transaction: TPointsTransaction) -> TPointsTransaction:
        """ИСПРАВЛЕНО: Создать транзакцию в БД (БЕЗ commit - делает middleware)"""
        try:
            self.session.add(transaction)
            await self.session.flush()  # Получаем ID
            # НЕ коммитим - это делает middleware!
            return transaction
        except Exception as e:
            logger.error(f"Error creating transaction: {e}")
            # НЕ откатываем - это делает middleware!
            raise

    async def update_user_balance(self, user_id: int, new_balance: int) -> bool:
        """ИСПРАВЛЕНО: Обновить баланс пользователя (БЕЗ commit - делает middleware)"""
        try:
            stmt = update(User).where(User.telegram_id == user_id).values(tpoints=new_balance)
            result = await self.session.execute(stmt)
            # НЕ коммитим - это делает middleware!
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating user balance {user_id}: {e}")
            # НЕ откатываем - это делает middleware!
            raise

    async def get_user_balance(self, user_id: int) -> Optional[int]:
        """Получить баланс пользователя"""
        try:
            query = select(User.tpoints).where(User.telegram_id == user_id)
            result = await self.session.execute(query)
            balance = result.scalar_one_or_none()
            return balance
        except Exception as e:
            logger.error(f"Error getting balance for user {user_id}: {e}")
            return None

    async def get_user_transactions(self, user_id: int, limit: int = 100) -> List[TPointsTransaction]:
        """Получить историю транзакций пользователя"""
        try:
            query = (
                select(TPointsTransaction)
                .options(
                    selectinload(TPointsTransaction.user),
                    selectinload(TPointsTransaction.product),
                    selectinload(TPointsTransaction.activity)
                )
                .where(TPointsTransaction.user_id == user_id)
                .order_by(TPointsTransaction.created_at.desc())
                .limit(limit)
            )
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting transactions for user {user_id}: {e}")
            return []

    async def get_transaction_by_id(self, transaction_id: int) -> Optional[TPointsTransaction]:
        """Получить транзакцию по ID"""
        try:
            query = (
                select(TPointsTransaction)
                .options(
                    selectinload(TPointsTransaction.user),
                    selectinload(TPointsTransaction.product),
                    selectinload(TPointsTransaction.activity)
                )
                .where(TPointsTransaction.id == transaction_id)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting transaction {transaction_id}: {e}")
            return None

    async def get_activities(self) -> List[TPointsActivity]:
        """Получить все активности для начисления T-Points"""
        try:
            query = select(TPointsActivity).where(TPointsActivity.is_active == True)
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting activities: {e}")
            return []

    async def create_transaction_with_balance_update(
        self, 
        transaction: TPointsTransaction, 
        new_balance: int
    ) -> Optional[TPointsTransaction]:
        """
        ИСПРАВЛЕНО: Атомарно создать транзакцию и обновить баланс пользователя
        БЕЗ commit - в рамках общей транзакции middleware
        """
        try:
            # Блокируем пользователя для обновления
            user = await self.get_user_by_id_for_update(transaction.user_id)
            if not user:
                logger.error(f"User {transaction.user_id} not found for balance update")
                return None
            
            # Добавляем транзакцию
            self.session.add(transaction)
            
            # Обновляем баланс в той же транзакции
            stmt = update(User).where(
                User.telegram_id == transaction.user_id
            ).values(tpoints=new_balance)
            
            result = await self.session.execute(stmt)
            
            if result.rowcount == 0:
                # Пользователь не найден (не должно произойти)
                logger.error(f"Failed to update balance for user {transaction.user_id}")
                return None
            
            # Получаем ID транзакции
            await self.session.flush()
            
            # НЕ коммитим - общий commit делает middleware!
            
            logger.info(f"Created transaction {transaction.id} and updated balance for user {transaction.user_id}")
            return transaction
            
        except Exception as e:
            logger.error(f"Error in atomic transaction creation: {e}")
            # НЕ откатываем - общий rollback делает middleware!
            raise

    async def get_recent_transactions(self, limit: int = 50) -> List[TPointsTransaction]:
        """Получить последние транзакции всех пользователей"""
        try:
            query = (
                select(TPointsTransaction)
                .options(
                    selectinload(TPointsTransaction.user),
                    selectinload(TPointsTransaction.product),
                    selectinload(TPointsTransaction.activity)
                )
                .order_by(TPointsTransaction.created_at.desc())
                .limit(limit)
            )
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting recent transactions: {e}")
            return []

    async def get_transactions_since_date(self, since_date) -> List[TPointsTransaction]:
        """Получить транзакции с определенной даты"""
        try:
            query = (
                select(TPointsTransaction)
                .options(
                    selectinload(TPointsTransaction.user),
                    selectinload(TPointsTransaction.product),
                    selectinload(TPointsTransaction.activity)
                )
                .where(TPointsTransaction.created_at >= since_date)
                .order_by(TPointsTransaction.created_at.desc())
            )
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting transactions since {since_date}: {e}")
            return []

    async def get_tpoints_stats(self) -> dict:
        """Получить статистику по T-Points"""
        try:
            # Общий баланс всех T-Points в системе
            total_points_query = select(func.sum(User.tpoints)).where(User.is_active == True)
            total_points_result = await self.session.execute(total_points_query)
            total_points = total_points_result.scalar() or 0
            
            # Количество активных пользователей с T-Points
            active_users_query = select(func.count(User.telegram_id)).where(
                User.is_active == True, 
                User.tpoints > 0
            )
            active_users_result = await self.session.execute(active_users_query)
            active_users = active_users_result.scalar() or 0
            
            # Количество транзакций за последний месяц
            month_ago = datetime.now() - timedelta(days=30)
            monthly_transactions_query = select(func.count(TPointsTransaction.id)).where(
                TPointsTransaction.created_at >= month_ago
            )
            monthly_transactions_result = await self.session.execute(monthly_transactions_query)
            monthly_transactions = monthly_transactions_result.scalar() or 0
            
            return {
                'total_points': total_points,
                'active_users': active_users,
                'monthly_transactions': monthly_transactions
            }
        except Exception as e:
            logger.error(f"Error getting T-Points stats: {e}")
            return {
                'total_points': 0,
                'active_users': 0,
                'monthly_transactions': 0
            }

    async def get_activity_by_id(self, activity_id: int) -> Optional[TPointsActivity]:
        """Получить активность по ID"""
        try:
            query = select(TPointsActivity).where(TPointsActivity.id == activity_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting activity {activity_id}: {e}")
            return None

    async def get_transactions_by_order(self, order_id: int) -> List[TPointsTransaction]:
        """Получить все транзакции связанные с заказом"""
        try:
            query = (
                select(TPointsTransaction)
                .options(
                    selectinload(TPointsTransaction.user),
                    selectinload(TPointsTransaction.product),
                    selectinload(TPointsTransaction.activity),
                    selectinload(TPointsTransaction.order)
                )
                .where(TPointsTransaction.order_id == order_id)
                .order_by(TPointsTransaction.created_at.desc())
            )
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting transactions for order {order_id}: {e}")
            return [] 