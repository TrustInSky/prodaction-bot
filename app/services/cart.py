from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.models import Cart, CartItem, Product
from ..core.base import BaseService
from ..repositories.cart_repository import CartRepository
import logging

logger = logging.getLogger(__name__)

class CartService(BaseService):
    """
    Сервис для работы с корзиной
    ИСПРАВЛЕНО: только бизнес-логика, работает через CartRepository
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.cart_repo = CartRepository(session)

    async def get_active_cart(self, user_id: int, refresh: bool = False) -> Optional[Cart]:
        """Получить активную корзину пользователя"""
        return await self.cart_repo.get_active_cart(user_id, refresh)

    async def get_cart_by_id(self, cart_id: int) -> Optional[Cart]:
        """Получить корзину по ID"""
        return await self.cart_repo.get_cart_by_id(cart_id)

    async def add_item(self, user_id: int, product_id: int, quantity: int = 1, size: Optional[str] = None) -> Optional[CartItem]:
        """
        Добавить товар в корзину
        Бизнес-логика: валидация количества
        """
        # Бизнес-логика: валидация
        if quantity <= 0:
            logger.warning(f"Invalid quantity {quantity} for user {user_id}")
            return None
            
        # Добавляем через репозиторий
        return await self.cart_repo.add_item(user_id, product_id, quantity, size)

    async def remove_item(self, user_id: int, product_id: int, size: Optional[str] = None) -> bool:
        """Удалить товар из корзины"""
        return await self.cart_repo.remove_item(user_id, product_id, size)

    async def clear_cart(self, user_id: int) -> bool:
        """Очистить корзину пользователя"""
        return await self.cart_repo.clear_cart(user_id)

    async def get_cart_item(self, user_id: int, product_id: int, size: Optional[str] = None) -> Optional[CartItem]:
        """Получить товар из корзины"""
        return await self.cart_repo.get_cart_item(user_id, product_id, size)

    async def get_cart_item_by_id(self, cart_item_id: int) -> Optional[CartItem]:
        """Получить элемент корзины по ID"""
        return await self.cart_repo.get_cart_item_by_id(cart_item_id)

    async def update_cart_item_quantity(self, user_id: int, product_id: int, size: Optional[str], quantity: int) -> bool:
        """
        Обновить количество товара в корзине
        Бизнес-логика: если количество 0 - удаляем товар
        """
        # Бизнес-логика: если количество 0 или меньше, удаляем товар
        if quantity <= 0:
            return await self.remove_item(user_id, product_id, size)
            
        # Обновляем через репозиторий
        result = await self.cart_repo.update_quantity(user_id, product_id, quantity, size)
        return result is not None

    async def update_cart_item_size(self, user_id: int, product_id: int, old_size: Optional[str], new_size: Optional[str]) -> bool:
        """
        Обновить размер товара в корзине
        Бизнес-логика: если размеры одинаковые - ничего не делаем
        """
        # Бизнес-логика: валидация
        if old_size == new_size:
            return True
            
        # Обновляем через репозиторий
        return await self.cart_repo.update_cart_item(user_id, product_id, old_size, new_size, 1)

    async def get_cart_total(self, user_id: int) -> float:
        """
        Получить общую стоимость корзины
        Бизнес-логика: расчет стоимости
        """
        try:
            cart = await self.get_active_cart(user_id)
            if not cart or not cart.items:
                return 0.0
                
            # Бизнес-логика: расчет общей стоимости
            total = sum(
                item.quantity * (item.product.price or 0)
                for item in cart.items
                if item.product
            )
            return total
        except Exception as e:
            logger.error(f"Error calculating cart total for user {user_id}: {e}")
            return 0.0

    async def get_cart_items_count(self, user_id: int) -> int:
        """
        Получить количество товаров в корзине
        Бизнес-логика: подсчет общего количества
        """
        try:
            cart = await self.get_active_cart(user_id)
            if not cart or not cart.items:
                return 0
                
            # Бизнес-логика: подсчет общего количества товаров
            return sum(item.quantity for item in cart.items)
        except Exception as e:
            logger.error(f"Error getting cart items count for user {user_id}: {e}")
            return 0

    async def validate_cart_for_checkout(self, user_id: int) -> tuple[bool, List[str]]:
        """
        Валидация корзины перед оформлением заказа
        Бизнес-логика: проверки доступности товаров
        """
        errors = []
        
        try:
            cart = await self.get_active_cart(user_id)
            if not cart:
                errors.append("Корзина не найдена")
                return False, errors
                
            if not cart.items:
                errors.append("Корзина пуста")
                return False, errors
            
            # Бизнес-логика: проверяем каждый товар в корзине
            for item in cart.items:
                if not item.product:
                    errors.append(f"Товар с ID {item.product_id} не найден")
                    continue
                    
                product = item.product
                
                # Проверяем доступность товара
                if not product.is_available:
                    errors.append(f"Товар '{product.name}' недоступен")
                    continue
                
                # Проверяем количество на складе
                if product.is_clothing() and item.size:
                    # Для одежды проверяем конкретный размер
                    available_qty = product.sizes_dict.get(item.size, 0)
                    if available_qty < item.quantity:
                        errors.append(
                            f"Товар '{product.name}' (размер {item.size}): "
                            f"недостаточно на складе. Доступно: {available_qty}, требуется: {item.quantity}"
                        )
                else:
                    # Для обычных товаров
                    available_qty = product.quantity_as_number
                    if available_qty < item.quantity:
                        errors.append(
                            f"Товар '{product.name}': "
                            f"недостаточно на складе. Доступно: {available_qty}, требуется: {item.quantity}"
                        )
            
            return len(errors) == 0, errors
            
        except Exception as e:
            logger.error(f"Error validating cart for user {user_id}: {e}")
            errors.append("Ошибка при проверке корзины")
            return False, errors

    async def check_cart_item_availability(self, cart_item_id: int) -> tuple[bool, int]:
        """
        Проверяет доступность конкретного товара в корзине
        
        Returns:
            tuple[bool, int]: (доступен ли товар, доступное количество)
        """
        try:
            cart_item = await self.get_cart_item_by_id(cart_item_id)
            if not cart_item or not cart_item.product:
                return False, 0
                
            product = cart_item.product
            
            # Бизнес-логика: проверка доступности
            if not product.is_available:
                return False, 0
            
            if product.is_clothing() and cart_item.size:
                available_quantity = product.sizes_dict.get(cart_item.size, 0)
            else:
                available_quantity = product.quantity_as_number
                
            is_available = available_quantity >= cart_item.quantity
            return is_available, available_quantity
            
        except Exception as e:
            logger.error(f"Error checking cart item {cart_item_id} availability: {e}")
            return False, 0