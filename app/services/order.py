from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime
from ..models.models import Order, OrderItem, Cart, CartItem, User, Product
from ..repositories.order_repository import OrderRepository
from ..repositories.cart_repository import CartRepository
from ..repositories.user_repository import UserRepository
from ..repositories.billing_repository import BillingRepository
from ..repositories.catalog_repository import CatalogRepository
from ..services.status_service import StatusService
from ..services.refund_service import RefundService
from ..core.base import BaseService
import logging

logger = logging.getLogger(__name__)

class OrderService(BaseService):
    """Сервис для работы с заказами - ИСПРАВЛЕНО: только бизнес-логика"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.order_repo = OrderRepository(session)
        self.cart_repo = CartRepository(session)
        self.user_repo = UserRepository(session)
        self.billing_repo = BillingRepository(session)
        self.catalog_repo = CatalogRepository(session)
        self.status_service = StatusService(session)
        self.refund_service = RefundService(session)
    
    async def get_orders(self, user_id: int = None, skip: int = 0, limit: int = 100) -> List[Order]:
        """Получить список заказов"""
        try:
            if user_id:
                return await self.order_repo.get_user_orders(user_id)
            else:
                return await self.order_repo.get_all_orders()
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []

    async def get_order_by_id(self, order_id: int, user_id: int = None) -> Optional[Order]:
        """Получить заказ по ID"""
        try:
            return await self.order_repo.get_order_by_id(order_id)
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None

    async def create_order_from_cart(self, cart_id: int, user_id: int) -> Optional[Order]:
        """
        Создать заказ из корзины
        ИСПРАВЛЕНО: только бизнес-логика, уведомления через очередь
        """
        try:
            # Получаем корзину
            cart = await self.cart_repo.get_cart_by_id(cart_id)
            if not cart or cart.user_id != user_id:
                logger.warning(f"Cart {cart_id} not found or access denied for user {user_id}")
                return None
                
            # Получаем элементы корзины из корзины
            cart_items = cart.items if cart.items else []
            if not cart_items:
                logger.warning(f"Cart {cart_id} is empty")
                return None
            
            # Вычисляем общую стоимость
            total_cost = sum(item.quantity * item.product.price for item in cart_items)

            # Получаем статус "новый" из БД
            new_status = await self.status_service.get_status_by_code('new')
            if not new_status:
                logger.error("Status 'new' not found in database")
                return None
            
            # Создаем заказ
            order_data = {
                'user_id': user_id,
                'total_cost': total_cost,
                'status_id': new_status.id,
                'status': 'new'  # Для совместимости
            }
            
            order = await self.order_repo.create_order(order_data, cart_items)
            if not order:
                logger.error(f"Failed to create order for user {user_id}")
                return None

            # Очищаем корзину
            await self.cart_repo.clear_cart(user_id)
                
            # Отправляем уведомление через очередь
            await self._send_order_created_notification(order, user_id)
                
            logger.info(f"Order {order.id} created successfully for user {user_id}")
            return order
            
        except Exception as e:
            logger.error(f"Error creating order from cart {cart_id}: {e}")
            return None

    async def _send_order_created_notification(self, order: Order, user_id: int):
        """Отправить уведомление о создании заказа через очередь"""
        try:
            from ..middlewares.database import add_pending_notification
            
            notification_data = {
                'order_id': order.id,
                'user_id': user_id,
                'order_total': float(order.total_cost)
            }
            
            add_pending_notification('order_created', notification_data)
            logger.info(f"Order {order.id} notification added to pending queue")
            
        except Exception as e:
            logger.error(f"Error adding notification for order {order.id}: {e}")

    async def update_order_status(self, order_id: int, new_status: str, hr_user_id: int = None) -> bool:
        """Обновить статус заказа с назначением HR и отправкой уведомлений"""
        try:
            # ИСПРАВЛЕНО: Получаем заказ ДО изменения статуса для определения старого статуса
            order_before = await self.order_repo.get_order_by_id(order_id)
            if not order_before:
                logger.error(f"Order {order_id} not found for status update")
                return False
            
            old_status = order_before.status
            
            # Обновляем статус в БД
            success = await self.order_repo.update_order_status(order_id, new_status, hr_user_id)
            if not success:
                return False
            
            # Логируем успешное обновление
            if hr_user_id and new_status == 'processing':
                logger.info(f"Order {order_id} status updated to {new_status} and assigned to HR {hr_user_id}")
            else:
                logger.info(f"Order {order_id} status updated to {new_status}")
            
            # ДОБАВЛЕНО: Отправляем уведомление о смене статуса
            try:
                # Получаем обновленный заказ с новым статусом
                updated_order = await self.order_repo.get_order_by_id(order_id)
                if updated_order:
                    await self._send_status_change_notification(updated_order, old_status, new_status)
                else:
                    logger.warning(f"Could not get updated order {order_id} for notification")
            except Exception as notification_error:
                logger.error(f"Error sending status change notification for order {order_id}: {notification_error}")
                # НЕ возвращаем False - статус обновлен успешно, проблема только с уведомлением
            
            return True
        except Exception as e:
            logger.error(f"Error updating order {order_id} status: {e}")
            return False

    async def cancel_order(self, order_id: int, user_id: int = None) -> bool:
        """ИСПРАВЛЕНО: Отменить заказ через репозиторий"""
        try:
            # Проверяем можно ли отменить заказ
            can_cancel = await self.order_repo.can_cancel_order(order_id)
            if not can_cancel:
                logger.warning(f"Cannot cancel order {order_id}")
                return False
            
            # Получаем данные для отмены
            order = await self.order_repo.get_order_with_details(order_id)
            if not order:
                logger.error(f"Order {order_id} not found for cancellation")
                return False
            
            # Возвращаем товары на склад
            await self._restore_order_products(order)
            
            # Обрабатываем возврат средств
            refund_success = await self.refund_service.process_order_refund(
                order_id, order.user_id, order.total_cost
            )
            if not refund_success:
                logger.error(f"Failed to process refund for order {order_id}")
                return False
            
            # Обновляем статус заказа
            status_updated = await self.order_repo.cancel_order(order_id)
            if not status_updated:
                logger.error(f"Failed to update order status for {order_id}")
                return False
            
            # Отправляем уведомление
            await self._send_status_change_notification(order, order.status, 'cancelled')
            
            logger.info(f"Order {order_id} successfully cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    async def _restore_order_products(self, order: Order) -> None:
        """ИСПРАВЛЕНО: Восстановить товары на складе для отмененного заказа"""
        try:
            logger.info(f"Restoring products for cancelled order {order.id}")
            
            for order_item in order.items:
                await self._restore_product_quantity(order_item)
            
            logger.info(f"All products restored for order {order.id}")
            
        except Exception as e:
            logger.error(f"Error restoring products for order {order.id}: {e}")
            raise

    async def get_user_orders(self, user_id: int, skip: int = 0, limit: int = 10) -> List[Order]:
        """Получить заказы пользователя"""
        try:
            return await self.order_repo.get_user_orders(user_id, skip, limit)
        except Exception as e:
            logger.error(f"Error getting orders for user {user_id}: {e}")
            return []

    async def get_order_statistics(self) -> Dict[str, Any]:
        """Получить статистику заказов"""
        try:
            stats = await self.order_repo.get_order_statistics()
            return stats
        except Exception as e:
            logger.error(f"Error getting order statistics: {e}")
            return {}

    async def search_orders(self, query: str, user_id: int = None) -> List[Order]:
        """Поиск заказов"""
        try:
            return await self.order_repo.search(query, user_id)
        except Exception as e:
            logger.error(f"Error searching orders: {e}")
            return []

    async def get_order_details(self, order_id: int, user_id: int = None) -> Optional[Dict[str, Any]]:
        """Получить детальную информацию о заказе"""
        try:
            order = await self.get_order_by_id(order_id, user_id)
            if not order:
                return None

            order_items = await self.order_repo.get_order_items(order_id)
            
            return {
                'order': order,
                'items': order_items,
                'total_items': len(order_items),
                'item_count': sum(item.quantity for item in order_items)
            }
        except Exception as e:
            logger.error(f"Error getting order details for {order_id}: {e}")
            return None

    def _check_item_availability(self, cart_item: CartItem) -> bool:
        """Проверить доступность товара"""
        if not cart_item.product:
            logger.error(f"CartItem {cart_item.id} has no product")
            return False
            
        product = cart_item.product
        
        if not product.is_available:
            logger.info(f"Product {product.id} is not available")
            return False
            
        if product.is_clothing():
            if not cart_item.size:
                logger.info(f"No size specified for clothing product {product.id}")
                return False
            
            sizes_dict = product.sizes_dict or {}
            available_quantity = sizes_dict.get(cart_item.size, 0)
            
            if available_quantity < cart_item.quantity:
                logger.info(f"Not enough stock for product {product.id}, size {cart_item.size}: need {cart_item.quantity}, have {available_quantity}")
                return False
        else:
            total_stock = product.total_stock or 0
            if total_stock < cart_item.quantity:
                logger.info(f"Not enough stock for product {product.id}: need {cart_item.quantity}, have {total_stock}")
                return False
        
        return True
            
    async def _update_product_quantity(self, cart_item: CartItem) -> None:
        """
        Обновить количество товара - ИСПРАВЛЕНО: через репозиторий
        """
        if not cart_item.product:
            logger.error(f"CartItem {cart_item.id} has no product")
            return
            
        product = cart_item.product
        
        try:
            if product.is_clothing() and cart_item.size:
                # Обновляем количество для конкретного размера через репозиторий
                sizes_dict = product.sizes_dict or {}
                if cart_item.size in sizes_dict:
                    new_quantity = max(0, sizes_dict[cart_item.size] - cart_item.quantity)
                    sizes_dict[cart_item.size] = new_quantity
                    await self.catalog_repo.update_product_sizes(product.id, sizes_dict)
                    logger.info(f"Updated size {cart_item.size} for product {product.id}: new quantity {new_quantity}")
            else:
                # Обновляем общее количество через репозиторий
                current_stock = product.total_stock or 0
                new_stock = max(0, current_stock - cart_item.quantity)
                await self.catalog_repo.update_product_quantity(product.id, new_stock)
                logger.info(f"Updated total stock for product {product.id}: new quantity {new_stock}")
        except Exception as e:
            logger.error(f"Error updating quantity for product {product.id}: {e}")
            # Не прерываем процесс из-за ошибки обновления количества
    
    async def assign_order_to_hr(self, order_id: int, hr_user_id: int) -> bool:
        """
        Назначить заказ HR-сотруднику и перевести в статус 'processing'
        """
        try:
            result = await self.update_order_status(order_id, 'processing', hr_user_id)
            return result is not None
        except Exception as e:
            logger.error(f"Error assigning order {order_id} to HR {hr_user_id}: {e}")
            return False
    
    async def mark_ready_for_pickup(self, order_id: int, hr_user_id: int) -> bool:
        """
        Отметить заказ готовым к выдаче
        """
        try:
            result = await self.update_order_status(order_id, 'ready_for_pickup', hr_user_id)
            return result is not None
        except Exception as e:
            logger.error(f"Error marking order {order_id} ready for pickup: {e}")
            return False
    
    async def mark_delivered(self, order_id: int, hr_user_id: int) -> bool:
        """
        Отметить заказ как выданный
        """
        try:
            result = await self.update_order_status(order_id, 'delivered', hr_user_id)
            return result is not None
        except Exception as e:
            logger.error(f"Error marking order {order_id} as delivered: {e}")
            return False
    
    async def _restore_order_products(self, order: Order) -> None:
        """
        Вернуть товары заказа на склад (БЕЗ commit)
        Middleware сделает общий commit ВСЕЙ операции
        """
        try:
            logger.info(f"Starting product restoration for order {order.id}")
            
            for order_item in order.items:
                await self._restore_product_quantity(order_item)
            
            logger.info(f"All products restored for order {order.id}")
                
        except Exception as e:
            logger.error(f"Error restoring products for order {order.id}: {e}")
            # При ошибке middleware сделает rollback ВСЕХ изменений
            raise
    
    async def _restore_product_quantity(self, order_item: OrderItem) -> None:
        """
        Вернуть товар на склад при отмене заказа - ИСПРАВЛЕНО: через репозиторий
        """
        if not order_item.product:
            logger.error(f"OrderItem {order_item.id} has no product")
            return
            
        product = order_item.product
        
        try:
            if product.is_clothing() and order_item.size:
                # Возвращаем количество для конкретного размера через репозиторий
                sizes_dict = product.sizes_dict or {}
                if order_item.size in sizes_dict:
                    sizes_dict[order_item.size] += order_item.quantity
                    logger.info(f"Restored size {order_item.size} for product {product.id}: +{order_item.quantity}")
                else:
                    # Если размера не было, создаем его
                    sizes_dict[order_item.size] = order_item.quantity
                    logger.info(f"Created size {order_item.size} for product {product.id}: {order_item.quantity}")
                
                await self.catalog_repo.update_product_sizes(product.id, sizes_dict)
            else:
                # Возвращаем общее количество через репозиторий
                current_stock = product.total_stock or 0
                new_stock = current_stock + order_item.quantity
                await self.catalog_repo.update_product_quantity(product.id, new_stock)
                
                # Если товар был недоступен, делаем его доступным через репозиторий
                if not product.is_available and new_stock > 0:
                    await self.catalog_repo.update_product_availability(product.id, True)
                    
                logger.info(f"Restored total stock for product {product.id}: +{order_item.quantity} (new total: {new_stock})")
                
        except Exception as e:
            logger.error(f"Error restoring quantity for product {product.id}: {e}")
            # Не прерываем процесс из-за ошибки восстановления количества
    
    async def _send_status_change_notification(self, order: Order, old_status: str, new_status: str) -> None:
        """Отправить уведомление пользователю об изменении статуса заказа"""
        try:
            from ..middlewares.database import add_pending_notification
            
            # Определяем тип уведомления на основе нового статуса
            notification_type = self._determine_notification_type(old_status, new_status)
            
            if notification_type:
                notification_data = {
                    'order_id': order.id,
                    'user_id': order.user_id,
                    'old_status': old_status,
                    'new_status': new_status,
                    'hr_user_id': order.hr_user_id
                }
                
                add_pending_notification(notification_type, notification_data)
                logger.info(f"Queued {notification_type} notification for order {order.id}")
            else:
                logger.debug(f"No notification defined for status change {old_status} -> {new_status}")
                
        except Exception as e:
            logger.error(f"Error sending status change notification for order {order.id}: {e}")
            # Не прерываем процесс из-за ошибки уведомления
    
    def _determine_notification_type(self, old_status: str, new_status: str) -> Optional[str]:
        """Определить тип уведомления по переходу статусов"""
        # Маппинг переходов статусов на типы уведомлений
        status_notifications = {
            'processing': 'order_taken',
            'ready_for_pickup': 'order_ready',
            'delivered': 'order_completed',
            'cancelled': 'order_cancelled'
        }
        
        return status_notifications.get(new_status)
    
    async def get_orders_by_status(self, status: str) -> List[Order]:
        """Получить все заказы по статусу через репозиторий"""
        try:
            return await self.order_repo.get_orders_by_status(status)
        except Exception as e:
            logger.error(f"Error getting orders by status {status}: {e}")
            return []
    
    async def get_all_orders(self) -> List[Order]:
        """Получить все заказы через репозиторий"""
        try:
            return await self.order_repo.get_all_orders()
        except Exception as e:
            logger.error(f"Error getting all orders: {e}")
            return []
    


    async def get_status_display_text(self, status_code: str) -> str:
        """Получить отображаемый текст статуса из БД"""
        try:
            status = await self.status_service.get_status_by_code(status_code)
            if status:
                return status.display_name
            return status_code  # Fallback
        except Exception as e:
            logger.error(f"Error getting status display text for {status_code}: {e}")
            return status_code

    
