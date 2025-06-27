"""
Константы для системы T-Points
"""

class TransactionType:
    """Типы транзакций T-Points"""
    
    # Основные операции
    PURCHASE = "purchase"           # Покупка товара
    REFUND = "refund"              # Возврат средств
    TOP_UP = "top_up"              # Пополнение баланса (админом)
    DEBIT = "debit"                # Списание (админом)
    EARNING = "earning"            # Начисление за активность
    
    @classmethod
    def get_display_name(cls, transaction_type: str) -> str:
        """Получить человекочитаемое название типа транзакции"""
        display_names = {
            cls.PURCHASE: "Покупка",
            cls.REFUND: "Возврат средств",
            cls.TOP_UP: "Пополнение",
            cls.DEBIT: "Списание", 
            cls.EARNING: "Начисление"
        }
        return display_names.get(transaction_type, transaction_type)
    
    @classmethod
    def get_all_types(cls) -> list:
        """Получить все доступные типы транзакций"""
        return [
            cls.PURCHASE,
            cls.REFUND,
            cls.TOP_UP,
            cls.DEBIT,
            cls.EARNING
        ]
    
    @classmethod
    def is_valid_type(cls, transaction_type: str) -> bool:
        """Проверить, является ли тип транзакции валидным"""
        return transaction_type in cls.get_all_types()