from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, Boolean, Date, ForeignKey, Text, DateTime, Float, JSON
from datetime import date, datetime
import json
import logging


Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    telegram_id = Column(Integer, primary_key=True, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=True)
    fullname = Column(String, nullable=False)
    birth_date = Column(Date, nullable=True)
    hire_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    tpoints = Column(Integer, default=0)
    department = Column(String, nullable=True)
    role = Column(String, nullable=False, default="user")

    orders = relationship("Order", foreign_keys="Order.user_id", back_populates="user")
    carts = relationship("Cart", back_populates="user")
    transactions = relationship("TPointsTransaction", back_populates="user")
    questions = relationship("Question", back_populates="user")
    answers = relationship("Answer", back_populates="respondent")



class Cart(Base):
    __tablename__ = "carts"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=False)
    is_active = Column(Boolean, default=True)
    
    @property
    def total_amount(self) -> int:
        """Вычисляет общую сумму корзины"""
        return sum(item.quantity * item.product.price for item in self.items)
    
    user = relationship("User", back_populates="carts")
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cart_id = Column(Integer, ForeignKey("carts.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    size = Column(String, nullable=True)
    color = Column(String, nullable=True)
    added_at = Column(DateTime, default=datetime.now)
    
    cart = relationship("Cart", back_populates="items")
    product = relationship("Product", back_populates="cart_items")


class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Integer, nullable=False)
    image_url = Column(String(500), nullable=True)
    is_available = Column(Boolean, default=True)
    size_quantities = Column(Text, nullable=True)  # JSON строка с размерами {"XL": 10, "L": 21} или просто число
    color = Column(String(50), nullable=True)
    
    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.name}', price={self.price})>"
    
    @property
    def sizes_dict(self):
        """Получить размеры как словарь"""
        if not self.size_quantities:
            return {}
        
        # Сначала проверяем, не является ли это просто числом
        try:
            int(self.size_quantities)
            # Если это число, возвращаем пустой словарь
            return {}
        except (ValueError, TypeError):
            # Если не число, пробуем парсить как JSON
            try:
                parsed = json.loads(self.size_quantities)
                # Проверяем, что это действительно словарь
                if isinstance(parsed, dict):
                    return parsed
                else:
                    return {}
            except json.JSONDecodeError as e:
                logging.error(f'JSONDecodeError in sizes_dict: {e} for product {self.id}')
                return {}
    
    @sizes_dict.setter
    def sizes_dict(self, value):
        """Установить размеры из словаря"""
        if value:
            self.size_quantities = json.dumps(value, ensure_ascii=False)
        else:
            self.size_quantities = None
    
    @property
    def quantity_as_number(self):
        """Получить size_quantities как число"""
        if not self.size_quantities:
            return 0
        try:
            # Пробуем преобразовать в число
            return int(self.size_quantities)
        except (ValueError, TypeError):
            # Если не число, возвращаем 0
            return 0
    
    @quantity_as_number.setter
    def quantity_as_number(self, value):
        """Установить size_quantities как число"""
        self.size_quantities = str(value) if value is not None else None
    
    def is_clothing(self):
        """Проверить, является ли товар одеждой (имеет размеры в JSON формате)"""
        return bool(self.size_quantities and self.sizes_dict)
    
    def has_quantity_number(self):
        """Проверить, содержит ли size_quantities просто число"""
        if not self.size_quantities:
            return False
        return not bool(self.sizes_dict) and self.quantity_as_number >= 0
    
    @property
    def total_stock(self):
        """Получить общее количество товара"""
        if not self.size_quantities:
            return 0
        
        # Сначала проверяем, является ли это числом
        try:
            # Пробуем получить как число
            number_quantity = int(self.size_quantities)
            return number_quantity
        except (ValueError, TypeError):
            # Если не число, пробуем как JSON словарь
            try:
                sizes = self.sizes_dict
                if sizes and isinstance(sizes, dict):
                    return sum(sizes.values())
                else:
                    return 0
            except (AttributeError, TypeError, KeyError) as e:
                # Логируем конкретную ошибку вместо глухого перехвата
                import logging
                logging.error(f"Error calculating total_stock for product {self.id}: {e}")
                return 0
    
    # Relationships
    order_items = relationship("OrderItem", back_populates="product")
    tpoints = relationship("TPointsTransaction", back_populates="product")
    cart_items = relationship("CartItem", back_populates="product")


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=False)
    total_cost = Column(Integer, nullable=False, default=0)
    status_id = Column(Integer, ForeignKey("order_statuses.id"), nullable=True)  # Ссылка на статус  
    status = Column(String, nullable=True)  # Временно оставляем для совместимости
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.now)
    hr_user_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=True)

    user = relationship("User", foreign_keys=[user_id], back_populates="orders")
    hr_user = relationship("User", foreign_keys=[hr_user_id])
    status_obj = relationship("OrderStatus", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    transactions = relationship("TPointsTransaction", back_populates="order")
    
    @property
    def status_code(self):
        """Получить код статуса для совместимости"""
        return self.status_obj.code if self.status_obj else self.status
    
    @property
    def status_display(self):
        """Получить отображаемое название статуса"""
        return self.status_obj.display_name if self.status_obj else self.status


class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    price = Column(Float, nullable=False)
    size = Column(String, nullable=True)
    color = Column(String, nullable=True)
    
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


class TPointsTransaction(Base):
    """Транзакции T-Points"""
    __tablename__ = "tpoints_transactions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    activity_id = Column(Integer, ForeignKey("tpoints_activities.id"), nullable=True)
    points_amount = Column(Integer, nullable=False)
    description = Column(String, nullable=False)
    transaction_type = Column(String, nullable=False, default="top_up")  # purchase, refund, top_up, debit, earning
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)  # Связь с заказом для покупок/возвратов
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    user = relationship("User", back_populates="transactions")
    product = relationship("Product", back_populates="tpoints")
    activity = relationship("TPointsActivity", back_populates="transactions")
    order = relationship("Order", back_populates="transactions")


class TPointsActivity(Base):
    """Типы активностей для начисления T-Points"""
    __tablename__ = "tpoints_activities"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(500), nullable=False, unique=True)
    points = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    transactions = relationship("TPointsTransaction", back_populates="activity")

    def __repr__(self):
        return f"<TPointsActivity(name='{self.name}', points={self.points})>"
    
    def to_dict(self):
        """Преобразует объект в словарь"""
        return {
            'id': self.id,
            'name': self.name,
            'points': self.points,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


class Question(Base):
    """Модель для анонимных вопросов"""
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=True)  # Может быть NULL для анонимных
    message = Column(Text, nullable=False)
    is_anonymous = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default='new')  # new, in_progress, answered
    
    user = relationship("User", back_populates="questions")
    answers = relationship("Answer", back_populates="question")


class Answer(Base):
    """Модель для ответов на вопросы"""
    __tablename__ = "answers"
    
    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    respondent_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    question = relationship("Question", back_populates="answers")
    respondent = relationship("User", back_populates="answers")














class OrderStatus(Base):
    """Статусы заказов - справочник"""
    __tablename__ = "order_statuses"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)  # new, processing, ready_for_pickup, delivered, cancelled
    name = Column(String(100), nullable=False)  # Отображаемое название
    emoji = Column(String(10), nullable=True)  # Эмодзи для статуса
    description = Column(Text, nullable=True)  # Описание статуса
    comment_user = Column(Text, nullable=True)  # Комментарий для пользователя
    comment_hr = Column(Text, nullable=True)  # Комментарий для HR
    is_active = Column(Boolean, default=True)
    order_index = Column(Integer, default=0)  # Порядок отображения
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связь с заказами
    orders = relationship("Order", back_populates="status_obj")
    
    def __repr__(self):
        return f"<OrderStatus(code='{self.code}', name='{self.name}')>"
    
    @property
    def display_name(self):
        """Отображаемое имя с эмодзи"""
        if self.emoji:
            return f"{self.emoji} {self.name}"
        return self.name


class NotificationType(Base):
    """Типы уведомлений - справочник"""
    __tablename__ = "notification_types"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)  # order_created, order_taken, etc.
    name = Column(String(100), nullable=False)  # Отображаемое название
    description = Column(Text, nullable=True)  # Описание типа уведомления
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<NotificationType(code='{self.code}', name='{self.name}')>"


class StatusTransition(Base):
    """Переходы между статусами и соответствующие уведомления"""
    __tablename__ = "status_transitions"
    
    id = Column(Integer, primary_key=True)
    from_status_id = Column(Integer, ForeignKey("order_statuses.id"), nullable=True)  # NULL = любой статус
    to_status_id = Column(Integer, ForeignKey("order_statuses.id"), nullable=False)
    notification_type_id = Column(Integer, ForeignKey("notification_types.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    from_status = relationship("OrderStatus", foreign_keys=[from_status_id])
    to_status = relationship("OrderStatus", foreign_keys=[to_status_id])
    notification_type = relationship("NotificationType")
    
    def __repr__(self):
        return f"<StatusTransition(from={self.from_status_id}, to={self.to_status_id})>"


class AutoEventSettings(Base):
    """Настройки автоматических событий (дни рождения, юбилеи, остатки)"""
    __tablename__ = "auto_event_settings"
    
    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), nullable=False, unique=True)  # 'birthday', 'anniversary', 'stock_low'
    is_enabled = Column(Boolean, default=True)
    
    # Настройки уведомлений  
    notification_days = Column(String, default="3,1,0")  # Дни напоминаний (через запятую)
    notification_time = Column(String, default="09:00")  # Время отправки уведомлений
    
    # Настройки T-Points
    tpoints_amount = Column(Integer, default=0)  # Базовая сумма T-Points
    tpoints_multiplier = Column(Integer, default=0)  # Множитель (для юбилеев - за каждый год)
    
    # Настройки остатков товаров
    stock_threshold = Column(Integer, default=5)  # Порог для уведомления об остатках
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<AutoEventSettings(event_type='{self.event_type}', is_enabled={self.is_enabled})>"


class AdminNotificationPreferences(Base):
    """Персональные настройки уведомлений для админов"""
    __tablename__ = "admin_notification_preferences"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=False, unique=True)
    
    # Персональные настройки админа (по умолчанию выключены для безопасности)
    birthday_enabled = Column(Boolean, default=False)
    anniversary_enabled = Column(Boolean, default=False)
    stock_enabled = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.now)
    
    user = relationship("User")
    
    def __repr__(self):
        return f"<AdminNotificationPreferences(user_id={self.user_id})>"


