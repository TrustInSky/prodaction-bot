from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ..models.models import Cart, CartItem, Product
from ..core.base import BaseRepository
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class CartRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_active_cart(self, user_id: int, refresh: bool = False) -> Optional[Cart]:
        """Получить активную корзину пользователя"""
        try:
            # Получаем корзину с предзагрузкой товаров
            query = (
                select(Cart)
                .options(selectinload(Cart.items).selectinload(CartItem.product))
                .where(Cart.user_id == user_id)
            )
            result = await self.session.execute(query)
            cart = result.scalar_one_or_none()
            
            if not cart:
                # Создаем новую корзину
                cart = Cart(user_id=user_id)
                self.session.add(cart)
                await self.session.flush()  # Не коммитим - middleware сделает
                
                # Принудительно инициализируем пустую коллекцию items
                # чтобы избежать ошибки MissingGreenlet
                cart.items = []
            elif refresh:
                # ИСПРАВЛЕНИЕ: Принудительно обновляем коллекцию items для свежих данных
                await self.session.refresh(cart, ["items"])
                
            return cart
        except Exception as e:
            logger.error(f"Error getting active cart for user {user_id}: {e}")
            return None

    async def get_cart_by_id(self, cart_id: int) -> Optional[Cart]:
        """Получить корзину по ID"""
        try:
            query = (
                select(Cart)
                .options(selectinload(Cart.items).selectinload(CartItem.product))
                .where(Cart.id == cart_id)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting cart by ID {cart_id}: {e}")
            return None

    async def get_cart_items(self, user_id: int) -> List[CartItem]:
        """Получить все товары в корзине пользователя"""
        try:
            # Получаем корзину
            cart = await self.get_active_cart(user_id)
            if not cart:
                return []
            
            # Получаем товары с предзагрузкой продуктов
            query = (
                select(CartItem)
                .options(selectinload(CartItem.product))
                .where(CartItem.cart_id == cart.id)
            )
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting cart items for user {user_id}: {e}")
            return []

    async def add_item(self, user_id: int, product_id: int, quantity: int, size: Optional[str] = None) -> Optional[CartItem]:
        """Добавить товар в корзину"""
        try:
            # Получаем корзину
            cart = await self.get_active_cart(user_id)
            if not cart:
                return None
            
            # Проверяем, есть ли уже такой товар в корзине
            query = (
                select(CartItem)
                .options(selectinload(CartItem.product))
                .where(
                    CartItem.cart_id == cart.id,
                    CartItem.product_id == product_id
                )
            )
            if size is not None:
                query = query.where(CartItem.size == size)
            
            result = await self.session.execute(query)
            existing_item = result.scalar_one_or_none()
            
            if existing_item:
                # Если товар уже есть, обновляем количество
                existing_item.quantity += quantity
                await self.session.flush()
                return existing_item
            else:
                # Если товара нет, создаем новый
                cart_item = CartItem(
                    cart_id=cart.id,
                    product_id=product_id,
                    quantity=quantity,
                    size=size
                )
                self.session.add(cart_item)
                await self.session.flush()
                return cart_item
        except Exception as e:
            logger.error(f"Error adding item to cart for user {user_id}: {e}")
            return None

    async def remove_item(self, user_id: int, product_id: int, size: Optional[str] = None) -> bool:
        """Удалить товар из корзины"""
        try:
            # Получаем корзину
            cart = await self.get_active_cart(user_id)
            if not cart:
                return False
            
            # Удаляем товар
            query = delete(CartItem).where(
                CartItem.cart_id == cart.id,
                CartItem.product_id == product_id
            )
            if size is not None:
                query = query.where(CartItem.size == size)
            
            result = await self.session.execute(query)
            
            if result.rowcount > 0:
                # ИСПРАВЛЕНИЕ: Принудительно обновляем коллекцию items в объекте cart
                # чтобы SQLAlchemy знала об изменениях в базе данных
                await self.session.refresh(cart, ["items"])
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error removing item from cart for user {user_id}: {e}")
            return False

    async def update_quantity(self, user_id: int, product_id: int, quantity: int, size: Optional[str] = None) -> Optional[CartItem]:
        """Обновить количество товара в корзине"""
        try:
            # Получаем корзину
            cart = await self.get_active_cart(user_id)
            if not cart:
                return None
            
            # Получаем товар из корзины
            query = (
                select(CartItem)
                .options(selectinload(CartItem.product))
                .where(
                    CartItem.cart_id == cart.id,
                    CartItem.product_id == product_id
                )
            )
            if size is not None:
                query = query.where(CartItem.size == size)
            
            result = await self.session.execute(query)
            cart_item = result.scalar_one_or_none()
            
            if cart_item:
                # Обновляем количество
                cart_item.quantity = quantity
                await self.session.flush()
                return cart_item
            return None
        except Exception as e:
            logger.error(f"Error updating quantity in cart for user {user_id}: {e}")
            return None

    async def clear_cart(self, user_id: int) -> bool:
        """Очистить корзину пользователя"""
        try:
            # Получаем корзину
            cart = await self.get_active_cart(user_id)
            if not cart:
                return False
            
            # Удаляем все товары
            query = delete(CartItem).where(CartItem.cart_id == cart.id)
            result = await self.session.execute(query)
            
            if result.rowcount > 0:
                # ИСПРАВЛЕНИЕ: Принудительно обновляем коллекцию items в объекте cart
                # чтобы SQLAlchemy знала об изменениях в базе данных
                await self.session.refresh(cart, ["items"])
                return True
                
            return False
        except Exception as e:
            logger.error(f"Error clearing cart for user {user_id}: {e}")
            return False

    async def get_cart_item(self, user_id: int, product_id: int, size: Optional[str] = None) -> Optional[CartItem]:
        """Получить конкретный товар из корзины"""
        try:
            # Получаем корзину
            cart = await self.get_active_cart(user_id)
            if not cart:
                return None
            
            # Получаем товар с предзагрузкой продукта
            query = (
                select(CartItem)
                .options(selectinload(CartItem.product))
                .where(
                    CartItem.cart_id == cart.id,
                    CartItem.product_id == product_id
                )
            )
            if size is not None:
                query = query.where(CartItem.size == size)
            
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting cart item for user {user_id}: {e}")
            return None

    async def get_cart_item_by_id(self, cart_item_id: int) -> Optional[CartItem]:
        """Получить элемент корзины по ID"""
        try:
            query = (
                select(CartItem)
                .options(
                    selectinload(CartItem.product),
                    selectinload(CartItem.cart)
                )
                .where(CartItem.id == cart_item_id)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting cart item by ID {cart_item_id}: {e}")
            return None

    async def get_cart_total(self, user_id: int) -> float:
        """Получить общую стоимость корзины"""
        try:
            cart_items = await self.get_cart_items(user_id)
            total = 0.0
            
            for item in cart_items:
                # Получаем информацию о товаре
                product_query = select(Product).where(Product.id == item.product_id)
                product_result = await self.session.execute(product_query)
                product = product_result.scalar_one_or_none()
                
                if product:
                    total += product.price * item.quantity
                    
            return total
        except Exception as e:
            logger.error(f"Error calculating cart total for user {user_id}: {e}")
            return 0.0

    async def update_cart_item(
        self,
        user_id: int,
        product_id: int,
        old_size: Optional[str],
        new_size: str,
        quantity: int
    ) -> bool:
        """Обновить размер товара в корзине"""
        try:
            # Получаем корзину
            cart = await self.get_active_cart(user_id)
            if not cart:
                return False
            
            # Получаем старый товар
            old_query = (
                select(CartItem)
                .options(selectinload(CartItem.product))
                .where(
                    CartItem.cart_id == cart.id,
                    CartItem.product_id == product_id
                )
            )
            if old_size is not None:
                old_query = old_query.where(CartItem.size == old_size)
            
            result = await self.session.execute(old_query)
            old_item = result.scalar_one_or_none()
            
            if not old_item:
                return False
            
            # Проверяем, есть ли уже товар с новым размером
            new_query = (
                select(CartItem)
                .options(selectinload(CartItem.product))
                .where(
                    CartItem.cart_id == cart.id,
                    CartItem.product_id == product_id,
                    CartItem.size == new_size
                )
            )
            result = await self.session.execute(new_query)
            existing_item = result.scalar_one_or_none()
            
            if existing_item:
                # Если товар с новым размером уже есть, обновляем его количество
                existing_item.quantity += old_item.quantity
                await self.session.delete(old_item)
            else:
                # Если товара с новым размером нет, обновляем старый
                old_item.size = new_size
            
            await self.session.flush()
            return True
            
        except Exception as e:
            logger.error(f"Error updating cart item for user {user_id}: {e}")
            return False 