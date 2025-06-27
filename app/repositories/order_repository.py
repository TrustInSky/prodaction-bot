from sqlalchemy import select, update, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from ..models.models import Order, OrderItem, User, Product
from ..core.base import BaseRepository
from typing import List, Optional, Dict, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class OrderRepository(BaseRepository):
    """Репозиторий для работы с заказами"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        
    async def create_order(self, order_data: dict, cart_items: List) -> Optional[Order]:
        """Создать новый заказ из данных и товаров корзины"""
        try:
            # Создаем заказ
            order = Order(**order_data)
            self.session.add(order)
            await self.session.flush()  # Получаем ID заказа
            
            # Добавляем товары в заказ
            for cart_item in cart_items:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=cart_item.product_id,
                    quantity=cart_item.quantity,
                    size=cart_item.size,
                    price=cart_item.product.price
                )
                self.session.add(order_item)
                
            await self.session.flush()
            return order
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return None

    async def get_order_by_id(self, order_id: int) -> Optional[Order]:
        """Получить заказ по ID с товарами"""
        try:
            query = (
                select(Order)
                .options(selectinload(Order.items).selectinload(OrderItem.product))
                .where(Order.id == order_id)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None

    async def update_order(self, order: Order) -> bool:
        """Обновить заказ"""
        try:
            await self.session.flush()
            return True
        except Exception as e:
            logger.error(f"Error updating order {order.id}: {e}")
            return False
            
    async def get_user_orders(self, user_id: int, skip: int = 0, limit: int = 100) -> List[Order]:
        """Получить заказы пользователя с пагинацией"""
        try:
            query = (
                select(Order)
                .options(selectinload(Order.items).selectinload(OrderItem.product))
                .where(Order.user_id == user_id)
                .order_by(Order.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting user orders for user {user_id}: {e}")
            return []
            
    async def get_order_items(self, order_id: int) -> List[OrderItem]:
        """Получить все товары в заказе"""
        try:
            query = (
                select(OrderItem)
                .options(joinedload(OrderItem.product))
                .where(OrderItem.order_id == order_id)
            )
            result = await self.session.execute(query)
            return list(result.unique().scalars().all())
        except Exception as e:
            logger.error(f"Error getting order items for order {order_id}: {e}")
            return []
            
    async def update_order_status(self, order_id: int, status: str, hr_user_id: int = None) -> bool:
        """Обновить статус заказа с назначением HR"""
        try:
            update_data = {'status': status}
            
            # Если передан hr_user_id и статус "processing", назначаем HR
            if hr_user_id and status == 'processing':
                update_data['hr_user_id'] = hr_user_id
            
            query = update(Order).where(Order.id == order_id).values(**update_data)
            await self.session.execute(query)
            return True
        except Exception as e:
            logger.error(f"Error updating order status for order {order_id}: {e}")
            return False

    async def get_order_with_details(self, order_id: int) -> Optional[Order]:
        """Получить заказ с полной информацией"""
        try:
            query = (
                select(Order)
                .options(
                    selectinload(Order.items).selectinload(OrderItem.product),
                    selectinload(Order.user),
                    selectinload(Order.hr_user),
                    selectinload(Order.status_obj)  # Добавляем загрузку статуса
                )
                .where(Order.id == order_id)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting order with details {order_id}: {e}")
            return None
            
    async def get_all_pending_orders(self) -> List[Order]:
        """Получить все новые заказы (ожидающие обработки)"""
        try:
            query = (
                select(Order)
                .options(
                    selectinload(Order.items).selectinload(OrderItem.product),
                    selectinload(Order.user)
                )
                .where(Order.status == 'new')
                .order_by(Order.created_at.desc())
            )
            result = await self.session.execute(query)
            return list(result.unique().scalars().all())
        except Exception as e:
            logger.error(f"Error getting pending orders: {e}")
            return []
            
    async def get_all_completed_orders(self) -> List[Order]:
        """Получить все выполненные заказы"""
        try:
            query = (
                select(Order)
                .options(
                    selectinload(Order.items).selectinload(OrderItem.product),
                    selectinload(Order.user)
                )
                .where(Order.status == 'delivered')
                .order_by(Order.created_at.desc())
            )
            result = await self.session.execute(query)
            return list(result.unique().scalars().all())
        except Exception as e:
            logger.error(f"Error getting completed orders: {e}")
            return []
            
    async def get_orders_by_status(self, status: str) -> List[Order]:
        """Получить все заказы с определенным статусом"""
        try:
            query = (
                select(Order)
                .options(
                    selectinload(Order.items).selectinload(OrderItem.product),
                    selectinload(Order.user)
                )
                .where(Order.status == status)
                .order_by(Order.created_at.desc())
            )
            result = await self.session.execute(query)
            return list(result.unique().scalars().all())
        except Exception as e:
            logger.error(f"Error getting orders by status {status}: {e}")
            return []
            
    async def get_all_orders(self) -> List[Order]:
        """Получить все заказы"""
        try:
            query = (
                select(Order)
                .options(
                    selectinload(Order.items).selectinload(OrderItem.product),
                    selectinload(Order.user)
                )
                .order_by(Order.created_at.desc())
            )
            result = await self.session.execute(query)
            return list(result.unique().scalars().all())
        except Exception as e:
            logger.error(f"Error getting all orders: {e}")
            return []
            
    async def get_analytics_by_departments(self) -> List[Tuple[str, int, int]]:
        """Получить аналитику по отделам"""
        async with self.session_factory() as session:
            query = (
                select(
                    User.department,
                    func.count(Order.id).label("orders_count"),
                    func.sum(Order.total_cost).label("total_spent")
                )
                .join(Order, Order.user_id == User.telegram_id)
                .where(Order.status != 'cancelled')
                .group_by(User.department)
                .order_by(desc("total_spent"))
            )
            result = await session.execute(query)
            return [(row[0] or "Без отдела", row[1], row[2]) for row in result.all()]
            
    async def get_top_products(self, limit: int = 10) -> List[Tuple[str, int, int]]:
        """Получить топ продаваемых товаров"""
        async with self.session_factory() as session:
            query = (
                select(
                    Product.name,
                    func.count(OrderItem.id).label("orders_count"),
                    func.sum(OrderItem.quantity).label("total_quantity")
                )
                .join(OrderItem, OrderItem.product_id == Product.id)
                .join(Order, Order.id == OrderItem.order_id)
                .where(Order.status != 'cancelled')
                .group_by(Product.id, Product.name)
                .order_by(desc("total_quantity"))
                .limit(limit)
            )
            result = await session.execute(query)
            return list(result.all())
            
    async def get_top_ambassadors(self, limit: int = 5) -> List[Tuple[str, str, int, int]]:
        """Получить топ амбассадоров"""
        async with self.session_factory() as session:
            query = (
                select(
                    User.fullname,
                    User.department,
                    func.count(Order.id).label("orders_count"),
                    func.sum(Order.total_cost).label("total_spent")
                )
                .join(Order, Order.user_id == User.telegram_id)
                .where(Order.status != 'cancelled')
                .group_by(User.telegram_id, User.fullname, User.department)
                .order_by(desc("total_spent"))
                .limit(limit)
            )
            result = await session.execute(query)
            return list(result.all())
            
    async def get_general_statistics(self) -> Dict[str, Any]:
        """Получить общую статистику"""
        async with self.session_factory() as session:
            # Общее количество заказов
            total_orders = await session.scalar(
                select(func.count(Order.id))
                .where(Order.status != 'cancelled')
            )
            
            # Общая сумма заказов
            total_spent = await session.scalar(
                select(func.sum(Order.total_cost))
                .where(Order.status != 'cancelled')
            )
            
            # Количество активных пользователей
            active_users = await session.scalar(
                select(func.count(func.distinct(Order.user_id)))
                .where(Order.status != 'cancelled')
            )
            
            # Средний чек
            avg_order = total_spent / total_orders if total_orders > 0 else 0
            
            return {
                "total_orders": total_orders,
                "total_spent": total_spent,
                "active_users": active_users,
                "avg_order": avg_order
            }

    async def cancel_order(self, order_id: int) -> bool:
        """Отменить заказ - обновить статус на 'cancelled'"""
        try:
            return await self.update_order_status(order_id, 'cancelled')
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    async def get_order_refund_amount(self, order_id: int) -> Optional[float]:
        """Получить сумму для возврата по заказу"""
        try:
            query = select(Order.total_cost).where(Order.id == order_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting refund amount for order {order_id}: {e}")
            return None

    async def get_order_items_for_cancellation(self, order_id: int) -> List[OrderItem]:
        """Получить товары заказа для отмены (с продуктами)"""
        try:
            query = (
                select(OrderItem)
                .options(selectinload(OrderItem.product))
                .where(OrderItem.order_id == order_id)
            )
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting order items for cancellation {order_id}: {e}")
            return []

    async def can_cancel_order(self, order_id: int) -> bool:
        """Проверить, можно ли отменить заказ"""
        try:
            order = await self.get_order_with_details(order_id)
            if not order:
                return False
            
            # Проверяем статус
            current_status = order.status_obj.code if order.status_obj else order.status
            return current_status not in ['cancelled', 'delivered']
        except Exception as e:
            logger.error(f"Error checking if order {order_id} can be cancelled: {e}")
            return False 