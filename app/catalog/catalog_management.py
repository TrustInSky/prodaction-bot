from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from ..services.excel_service import ExcelService
from ..services.catalog import CatalogService
from ..services.user import UserService
from .keyboards.catalog_management_kb import CatalogManagementKeyboard
from ..utils.message_editor import update_message
from ..utils.callback_helpers import safe_callback_answer
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

catalog_management_router = Router(name="catalog_management")

class CatalogManagementStates(StatesGroup):
    waiting_for_excel = State()

@catalog_management_router.callback_query(F.data == "menu:catalog_management")
async def show_catalog_management(callback: CallbackQuery, user_service: UserService):
    """Показать меню управления каталогом - рефакторинг: aiogram3-di"""
    try:
        logger.info(f"🎯 CATALOG MANAGEMENT HANDLER TRIGGERED! User {callback.from_user.id} callback: {callback.data}")
        
        # Проверяем роль пользователя
        user = await user_service.get_user(callback.from_user.id)
        if not user or user.role not in ['hr', 'admin']:
            logger.warning(f"🚫 Access denied for user {callback.from_user.id}, role: {user.role if user else 'None'}")
            await safe_callback_answer(callback, "❌ Доступ запрещен", show_alert=True)
            return
        
        text = (
            "📊 <b>Управление каталогом</b>\n\n"
            "Выберите действие:\n"
            "• 📥 Загрузить товары из Excel\n"
            "• 📤 Выгрузить текущий каталог\n\n"
            "💡 <b>Поддерживаемые форматы:</b>\n"
            "• Excel файлы (.xlsx, .xls)\n"
            "• Автоматическая обработка размеров\n"
            "• Конвертация Google Drive ссылок в image_url"
        )
        
        keyboard = CatalogManagementKeyboard.get_management_keyboard()
        await update_message(callback, text=text, reply_markup=keyboard)
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error showing catalog management: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка")

@catalog_management_router.callback_query(F.data == "catalog:upload_excel")
async def request_excel_file(callback: CallbackQuery, state: FSMContext, user_service: UserService):
    """Запросить Excel файл для загрузки - рефакторинг: aiogram3-di"""
    try:
        # Проверяем роль пользователя
        user = await user_service.get_user(callback.from_user.id)
        if not user or user.role not in ['hr', 'admin']:
            await safe_callback_answer(callback, "❌ Доступ запрещен", show_alert=True)
            return
            
        await state.set_state(CatalogManagementStates.waiting_for_excel)
        
        text = (
            "📥 <b>Загрузка товаров из Excel</b>\n\n"
            "Отправьте Excel файл с товарами.\n\n"
            "📋 <b>Обязательные колонки:</b>\n"
            "• <code>name</code> - название товара\n"
            "• <code>price</code> - цена в T-Points\n\n"
            "📋 <b>Дополнительные колонки:</b>\n"
            "• <code>description</code> - описание\n"
            "• <code>image_url</code> - ссылка на изображение\n"
            "• <code>color</code> - цвет товара\n"
            "• <code>sizes</code> - размеры (формат: S:10,M:20,L:15)\n"
            "• <code>quantity</code> - количество (для товаров без размеров)\n"
            "• <code>is_available</code> - доступность (true/false)\n\n"
            "🔗 <b>Google Drive ссылки в image_url автоматически конвертируются!</b>"
        )
        
        keyboard = CatalogManagementKeyboard.get_cancel_keyboard()
        await update_message(callback, text=text, reply_markup=keyboard)
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error requesting Excel file: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка")

@catalog_management_router.message(CatalogManagementStates.waiting_for_excel, F.document)
async def handle_excel_upload(
    message: Message, 
    state: FSMContext, 
    excel_service: ExcelService,
    catalog_service: CatalogService,
    user_service: UserService
):
    """Обработка загруженного Excel файла - рефакторинг: aiogram3-di"""
    try:
        # Проверяем роль пользователя
        user = await user_service.get_user(message.from_user.id)
        if not user or user.role not in ['hr', 'admin']:
            await message.answer("❌ Доступ запрещен")
            await state.clear()
            return
            
        # Проверяем тип файла
        if not message.document.file_name.endswith(('.xlsx', '.xls')):
            await message.answer("❌ Пожалуйста, отправьте файл Excel (.xlsx или .xls)")
            return
            
        await message.answer("⏳ Обрабатываю файл...")
        
        # Создаем папку temp если не существует
        os.makedirs("temp", exist_ok=True)
        
        # Скачиваем файл
        file = await message.bot.get_file(message.document.file_id)
        file_path = f"temp/{message.document.file_name}"
        await message.bot.download_file(file.file_path, file_path)
        
        # Импортируем товары
        products = await excel_service.import_products_from_excel(file_path)
        
        # Удаляем временный файл СРАЗУ после обработки
        try:
            os.remove(file_path)
            logger.info(f"Temporary file {file_path} deleted")
        except Exception as e:
            logger.warning(f"Failed to delete temporary file {file_path}: {e}")
        
        if not products:
            await message.answer("❌ Не удалось найти товары в файле")
            await state.clear()
            return
        
        # Обновляем базу данных
        updated_count = await catalog_service.bulk_update_products(products)
        
        # Очищаем состояние
        await state.clear()
        
        # Отправляем отчет
        text = (
            "✅ <b>Загрузка завершена успешно!</b>\n\n"
            f"📊 Обработано товаров: <b>{len(products)}</b>\n"
            f"💾 Обновлено в базе: <b>{updated_count}</b>\n\n"
            f"📝 Детали:\n"
            f"• Новые товары добавлены\n"
            f"• Существующие товары обновлены\n"
            f"• Google Drive ссылки конвертированы\n"
            f"• Размеры и количество обработаны\n"
            f"• Временный файл удален"
        )
        
        keyboard = CatalogManagementKeyboard.get_management_keyboard()
        await message.answer(text=text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error handling Excel upload: {e}")
        await message.answer(f"❌ Произошла ошибка при обработке файла:\n<code>{str(e)}</code>")
        await state.clear()
        
        # Пытаемся удалить временный файл даже при ошибке
        try:
            if 'file_path' in locals():
                os.remove(file_path)
        except:
            pass

@catalog_management_router.callback_query(F.data == "catalog:export")
async def export_catalog(callback: CallbackQuery, excel_service: ExcelService, user_service: UserService):
    """Выгрузка каталога в Excel - рефакторинг: aiogram3-di"""
    try:
        # Проверяем роль пользователя
        user = await user_service.get_user(callback.from_user.id)
        if not user or user.role not in ['hr', 'admin']:
            await safe_callback_answer(callback, "❌ Доступ запрещен", show_alert=True)
            return
        
        # Показываем временное сообщение о формировании файла
        await update_message(
            callback,
            text="⏳ Формирую Excel файл...",
            reply_markup=None
        )
        
        # Получаем Excel файл как BytesIO
        excel_buffer = await excel_service.export_products_to_excel()
        
        # Формируем имя файла
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"catalog_export_{current_time}.xlsx"
        
        # Создаем BufferedInputFile для отправки
        excel_file = BufferedInputFile(
            file=excel_buffer.getvalue(),
            filename=filename
        )
        
        # Отправляем файл
        await callback.message.answer_document(
            document=excel_file,
            caption=(
                f"📊 <b>Выгрузка каталога товаров</b>\n\n"
                f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"📋 Файл содержит все товары из базы данных\n"
                f"🔄 Готов для редактирования и повторной загрузки"
            )
        )
        
        # Показываем меню после успешной выгрузки
        keyboard = CatalogManagementKeyboard.get_management_keyboard()
        await callback.message.answer(
            text="✅ Каталог успешно выгружен! Что дальше?",
            reply_markup=keyboard
        )
        
        logger.info(f"Catalog exported successfully: {filename}")
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error exporting catalog: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при выгрузке каталога", show_alert=True) 

@catalog_management_router.callback_query(F.data == "catalog:cancel")
async def cancel_operation(callback: CallbackQuery, state: FSMContext, user_service: UserService):
    """Отмена операции - рефакторинг: aiogram3-di"""
    try:
        # Проверяем роль пользователя
        user = await user_service.get_user(callback.from_user.id)
        if not user or user.role not in ['hr', 'admin']:
            await safe_callback_answer(callback, "❌ Доступ запрещен", show_alert=True)
            return
            
        await state.clear()
        
        text = (
            "❌ <b>Операция отменена</b>\n\n"
            "Возвращаемся к меню управления каталогом."
        )
        
        keyboard = CatalogManagementKeyboard.get_management_keyboard()
        await update_message(callback, text=text, reply_markup=keyboard)
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error canceling operation: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка") 