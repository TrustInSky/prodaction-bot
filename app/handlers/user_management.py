from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from ..services.user_manager_service import UserManagerService
from ..utils.message_editor import update_message
from ..utils.callback_helpers import safe_callback_answer
from ..middlewares.access_control import HROrAdminAccess
from ..keyboards.user_management_kb import UserManagementKeyboard
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

user_management_router = Router(name="user_management")

# Регистрируем middleware для проверки доступа
user_management_router.callback_query.middleware(HROrAdminAccess())
user_management_router.message.middleware(HROrAdminAccess())

# Определение состояний
class UserManagementStates(StatesGroup):
    awaiting_users_excel_upload = State()
    awaiting_tpoints_excel_upload = State()


# ===== ГЛАВНЫЕ МЕНЮ =====

@user_management_router.callback_query(F.data == "menu:users")
async def show_users_management_menu(callback: CallbackQuery, user_manager_service: UserManagerService):
    """Показать главное меню управления сотрудниками"""
    try:
        logger.info(f"User {callback.from_user.id} opening users management menu")
        
        # Получаем статистику по пользователям через UserService
        from ..services.user import UserService
        user_service = UserService(user_manager_service.session)
        stats = await user_service.get_users_stats()
        
        text = (
            f"👥 <b>Управление сотрудниками</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• Всего сотрудников: {stats.get('total_users', 0)}\n"
            f"• Активных: {stats.get('active_users', 0)}\n"
            f"• По отделам: {stats.get('departments_count', 0)}\n\n"
            f"🛠 Выберите действие:"
        )
        
        keyboard = UserManagementKeyboard.get_users_management_menu()
        
        await update_message(callback, text=text, reply_markup=keyboard)
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error showing users management menu: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Ошибка при загрузке меню", show_alert=True)


@user_management_router.callback_query(F.data == "menu:tpoints") 
async def show_tpoints_management_menu(callback: CallbackQuery, user_manager_service: UserManagerService):
    """Показать главное меню управления T-Points"""
    try:
        logger.info(f"User {callback.from_user.id} opening T-Points management menu")
        
        # Получаем статистику по T-Points через TransactionService
        from ..services.transaction_service import TransactionService
        transaction_service = TransactionService(user_manager_service.session)
        stats = await transaction_service.get_tpoints_stats()
        
        text = (
            f"💎 <b>Управление T-Points</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• Общий баланс: {stats.get('total_points', 0):,} T-Points\n"
            f"• Активных пользователей: {stats.get('active_users', 0)}\n"
            f"• Транзакций за месяц: {stats.get('monthly_transactions', 0)}\n\n"
            f"🛠 Выберите действие:"
        )
        
        keyboard = UserManagementKeyboard.get_tpoints_management_menu()
        
        await update_message(callback, text=text, reply_markup=keyboard)
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error showing T-Points management menu: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Ошибка при загрузке меню", show_alert=True)


@user_management_router.callback_query(F.data == "users:export")
async def export_users(callback: CallbackQuery, user_manager_service: UserManagerService):
    """Экспорт пользователей в Excel"""
    try:
        logger.info(f"User {callback.from_user.id} exporting users")
        
        # Показываем сообщение о начале экспорта
        await update_message(
            callback,
            text="📊 Генерируем файл с данными сотрудников...",
            reply_markup=None
        )
        
        # Генерируем Excel файл
        excel_buffer = await user_manager_service.export_users_to_excel()
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
            temp_file.write(excel_buffer.getvalue())
            temp_file_path = temp_file.name
        
        # Отправляем файл
        await callback.message.answer_document(
            document=FSInputFile(temp_file_path, filename="employees.xlsx"),
            caption="📤 <b>Экспорт сотрудников</b>\n\nДанные сотрудников по отделам"
        )
        
        # Удаляем временный файл
        os.remove(temp_file_path)
        
        # Показываем меню
        keyboard = UserManagementKeyboard.get_users_export_menu()
        
        await callback.message.answer(
            text="✅ Файл выгружен! Что дальше?",
            reply_markup=keyboard
        )
        
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error exporting users: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Ошибка при экспорте данных", show_alert=True)


@user_management_router.callback_query(F.data == "users:import")
async def request_users_upload(callback: CallbackQuery, state: FSMContext):
    """Запрос загрузки Excel файла с пользователями"""
    try:
        logger.info(f"User {callback.from_user.id} requesting users import")
        
        text = (
            "📥 <b>Импорт сотрудников</b>\n\n"
            "Пришлите Excel-файл с данными сотрудников (.xlsx)\n\n"
            "📋 <b>Требования к файлу:</b>\n"
            "• Формат: .xlsx\n"
            "• Данные разбиты по листам по отделам\n"
            "• Обязательные поля: telegram_id, fullname\n"
            "• Пустые поля будут выделены красным"
        )
        
        keyboard = UserManagementKeyboard.get_users_import_cancel()
        
        await update_message(callback, text=text, reply_markup=keyboard)
        await state.set_state(UserManagementStates.awaiting_users_excel_upload)
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error requesting users upload: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Ошибка", show_alert=True)


@user_management_router.callback_query(F.data == "tpoints:template")
async def export_tpoints_template(callback: CallbackQuery, user_manager_service: UserManagerService):
    """Экспорт шаблона для T-Points операций"""
    try:
        logger.info(f"User {callback.from_user.id} exporting T-Points template")
        
        # Показываем сообщение о начале экспорта
        await update_message(
            callback,
            text="📋 Генерируем шаблон для T-Points операций...",
            reply_markup=None
        )
        
        # Генерируем шаблон Excel файла
        excel_buffer = await user_manager_service.export_tpoints_template_to_excel()
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
            temp_file.write(excel_buffer.getvalue())
            temp_file_path = temp_file.name
        
        # Отправляем файл
        await callback.message.answer_document(
            document=FSInputFile(temp_file_path, filename="tpoints_template.xlsx"),
            caption="📋 <b>Шаблон T-Points операций</b>\n\nЗаполните данные и отправьте обратно"
        )
        
        # Удаляем временный файл
        os.remove(temp_file_path)
        
        # Показываем меню
        keyboard = UserManagementKeyboard.get_tpoints_export_menu()
        
        await callback.message.answer(
            text="✅ Шаблон выгружен! Что дальше?",
            reply_markup=keyboard
        )
        
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error exporting T-Points template: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Ошибка при экспорте шаблона", show_alert=True)


@user_management_router.callback_query(F.data == "tpoints:import")
async def request_tpoints_upload(callback: CallbackQuery, state: FSMContext):
    """Запрос загрузки Excel файла с T-Points операциями"""
    try:
        logger.info(f"User {callback.from_user.id} requesting T-Points import")
        
        text = (
            "💎 <b>Импорт T-Points операций</b>\n\n"
            "Пришлите заполненный Excel-файл с T-Points операциями (.xlsx)\n\n"
            "📋 <b>Требования к файлу:</b>\n"
            "• Формат: .xlsx\n"
            "• Данные разбиты по листам по отделам\n"
            "• Обязательные поля: telegram_id, points_to_add, reason\n"
            "• Положительные числа - начисление, отрицательные - списание"
        )
        
        keyboard = UserManagementKeyboard.get_tpoints_import_cancel()
        
        await update_message(callback, text=text, reply_markup=keyboard)
        await state.set_state(UserManagementStates.awaiting_tpoints_excel_upload)
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error requesting T-Points upload: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Ошибка", show_alert=True)


@user_management_router.message(F.document, StateFilter(UserManagementStates.awaiting_users_excel_upload))
async def handle_users_excel_upload(message: Message, state: FSMContext, user_manager_service: UserManagerService):
    """Обработка загрузки Excel файла с пользователями"""
    try:
        file = message.document
        logger.info(f"Received users file: {file.file_name}")
        
        if not file.file_name.endswith(".xlsx"):
            await message.answer("❌ Пожалуйста, отправьте файл в формате .xlsx")
            return
        
        # Создаем временный файл
        file_path = f"/tmp/users_{file.file_name}"
        
        try:
            await message.bot.download(file, destination=file_path)
            logger.info(f"File saved to: {file_path}")
            
            if not os.path.exists(file_path):
                await message.answer("❌ Ошибка: не удалось сохранить файл")
                return
                
        except Exception as download_error:
            logger.error(f"Error downloading file: {download_error}")
            await message.answer(f"❌ Ошибка при загрузке файла: {str(download_error)}")
            return
        
        # Показываем сообщение о начале обработки
        processing_msg = await message.answer("⚙️ Обрабатываем файл...")
        
        try:
            # Читаем файл в память
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Предварительный просмотр изменений
            preview = await user_manager_service.preview_users_import(file_content)
            
            if preview['errors'] and len(preview['errors']) > 0:
                error_text = "❌ Критические ошибки в файле:\n" + "\n".join(preview['errors'][:5])
                if len(preview['errors']) > 5:
                    error_text += f"\n... и ещё {len(preview['errors']) - 5} ошибок"
                await message.answer(error_text)
                return
            
            if not preview['users_to_update']:
                await message.answer("ℹ️ В файле не найдено изменений для обновления.")
                return
            
            # Показываем предварительный просмотр изменений
            preview_text = (
                "📋 <b>ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР ИЗМЕНЕНИЙ СОТРУДНИКОВ</b>\n\n"
                f"📊 <b>Сводка:</b>\n"
                f"• Пользователей для обновления: {preview['total_users']}\n"
            )
            
            if preview['warnings']:
                preview_text += f"⚠️ Предупреждений: {len(preview['warnings'])}\n"
            
            preview_text += "\n<b>🔍 Детали изменений (первые 5):</b>\n"
            
            for i, user_update in enumerate(preview['users_to_update'][:5], 1):
                preview_text += f"{i}. <b>{user_update['fullname']}</b> (@{user_update['username'] or 'без username'})\n"
                
                for field, change in user_update['changes'].items():
                    field_name = {
                        'fullname': 'Имя',
                        'birth_date': 'Дата рождения',
                        'hire_date': 'Дата трудоустройства',
                        'department': 'Отдел',
                        'is_active': 'Активность'
                    }.get(field, field)
                    
                    preview_text += f"   • {field_name}: '{change['old']}' → '{change['new']}'\n"
                
                if user_update['warnings']:
                    for warning in user_update['warnings']:
                        preview_text += f"   ⚠️ {warning}\n"
                
                preview_text += "\n"
            
            if len(preview['users_to_update']) > 5:
                preview_text += f"... и ещё {len(preview['users_to_update']) - 5} пользователей\n\n"
            
            preview_text += (
                "⚠️ <b>ВНИМАНИЕ:</b>\n"
                "• Изменения будут применены немедленно\n"
                "• Отменить изменения будет невозможно\n\n"
                "Проверьте данные и подтвердите импорт:"
            )
            
            # Кнопки для подтверждения или отмены
            # Сохраняем файл через менеджер временных файлов
            from ..utils.temp_file_manager import temp_file_manager
            file_id = temp_file_manager.store_file(file_path, ttl_minutes=30)
            
            keyboard = UserManagementKeyboard.get_users_confirm_import(file_id)
            
            await message.answer(preview_text, reply_markup=keyboard)
            
        except Exception as processing_error:
            logger.error(f"Error processing users file: {processing_error}")
            await message.answer(f"❌ Ошибка при обработке файла: {str(processing_error)}")
        finally:
            # НЕ удаляем файл здесь - он нужен для подтверждения импорта
            pass
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Critical error handling users upload: {e}", exc_info=True)
        await message.answer(f"❌ Произошла критическая ошибка: {str(e)}")
        await state.clear()


@user_management_router.message(F.document, StateFilter(UserManagementStates.awaiting_tpoints_excel_upload))
async def handle_tpoints_excel_upload(message: Message, state: FSMContext, user_manager_service: UserManagerService):
    """Обработка загрузки Excel файла с T-Points операциями"""
    try:
        file = message.document
        logger.info(f"Received T-Points file: {file.file_name}")
        
        if not file.file_name.endswith(".xlsx"):
            await message.answer("❌ Пожалуйста, отправьте файл в формате .xlsx")
            return
        
        # Создаем временный файл
        file_path = f"/tmp/tpoints_{file.file_name}"
        
        try:
            await message.bot.download(file, destination=file_path)
            logger.info(f"File saved to: {file_path}")
            
            if not os.path.exists(file_path):
                await message.answer("❌ Ошибка: не удалось сохранить файл")
                return
                
        except Exception as download_error:
            logger.error(f"Error downloading file: {download_error}")
            await message.answer(f"❌ Ошибка при загрузке файла: {str(download_error)}")
            return
        
        # Показываем сообщение о начале обработки
        processing_msg = await message.answer("⚙️ Анализируем T-Points операции...")
        
        try:
            # Читаем файл в память
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Предварительный просмотр изменений
            preview = await user_manager_service.preview_tpoints_changes(file_content)
            
            if preview['errors'] and len(preview['errors']) > 0:
                error_text = "❌ Ошибки в файле:\n" + "\n".join(preview['errors'][:5])
                if len(preview['errors']) > 5:
                    error_text += f"\n... и ещё {len(preview['errors']) - 5} ошибок"
                await message.answer(error_text)
                return
            
            # Показываем детальный предварительный просмотр
            total_add = preview['total_points_add']
            total_remove = preview['total_points_remove']
            net_change = total_add - total_remove
            
            preview_text = (
                "📋 <b>ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР T-POINTS ОПЕРАЦИЙ</b>\n\n"
                f"📊 <b>Сводка:</b>\n"
                f"• Всего операций: {preview['total_operations']}\n"
                f"• 💰 Начислений: {total_add:,} T-Points\n"
                f"• 💸 Списаний: {total_remove:,} T-Points\n"
                f"• 📈 Итоговое изменение: {net_change:+,} T-Points\n\n"
            )
            
            if preview['errors']:
                preview_text += f"⚠️ <b>Ошибок в файле: {len(preview['errors'])}</b>\n"
                for error in preview['errors'][:3]:
                    preview_text += f"• {error}\n"
                if len(preview['errors']) > 3:
                    preview_text += f"... и ещё {len(preview['errors']) - 3} ошибок\n"
                preview_text += "\n"
            
            if preview['operations']:
                preview_text += "<b>🔍 Детали операций (первые 5):</b>\n"
                for i, op in enumerate(preview['operations'][:5], 1):
                    action_emoji = "💰" if op['points_change'] > 0 else "💸"
                    action = "Начисление" if op['points_change'] > 0 else "Списание"
                    
                    preview_text += (
                        f"{i}. {action_emoji} <b>{op['fullname']}</b>\n"
                        f"   📝 {op['reason']}\n"
                        f"   💎 {op['current_points']:,} → {op['new_points']:,} T-Points "
                        f"({op['points_change']:+,})\n\n"
                    )
                
                if len(preview['operations']) > 5:
                    preview_text += f"... и ещё {len(preview['operations']) - 5} операций\n\n"
            
            preview_text += (
                "⚠️ <b>ВНИМАНИЕ:</b>\n"
                "• Операции будут выполнены немедленно\n"
                "• Пользователи получат уведомления\n"
                "• Отменить операции будет невозможно\n\n"
                "Проверьте данные и подтвердите выполнение:"
            )
            
            # Кнопки для подтверждения или отмены
            # Сохраняем файл через менеджер временных файлов
            from ..utils.temp_file_manager import temp_file_manager
            file_id = temp_file_manager.store_file(file_path, ttl_minutes=30)
            
            keyboard = UserManagementKeyboard.get_tpoints_confirm_operations(file_id)
            
            await message.answer(preview_text, reply_markup=keyboard)
            
        except Exception as processing_error:
            logger.error(f"Error processing T-Points file: {processing_error}")
            await message.answer(f"❌ Ошибка при обработке файла: {str(processing_error)}")
        finally:
            # НЕ удаляем файл здесь - он нужен для подтверждения операций
            pass
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Critical error handling T-Points upload: {e}", exc_info=True)
        await message.answer(f"❌ Произошла критическая ошибка: {str(e)}")
        await state.clear()


@user_management_router.callback_query(F.data.startswith("tpoints:confirm:"))
async def confirm_tpoints_operations(callback: CallbackQuery, user_manager_service: UserManagerService):
    """Подтверждение и применение T-Points операций"""
    try:
        from ..utils.temp_file_manager import temp_file_manager
        file_id = callback.data.replace("tpoints:confirm:", "")
        file_path = temp_file_manager.get_file_path(file_id)
        
        if not file_path:
            await safe_callback_answer(callback, "❌ Файл не найден или истек срок действия", show_alert=True)
            return
        
        logger.info(f"Confirming T-Points operations from file: {file_path}")
        
        if not os.path.exists(file_path):
            temp_file_manager.remove_file(file_id)
            await safe_callback_answer(callback, "❌ Файл не найден", show_alert=True)
            return
        
        # Показываем сообщение о выполнении операций
        await update_message(
            callback,
            text="⚙️ Выполняем T-Points операции...",
            reply_markup=None
        )
        
        try:
            # Читаем файл в память
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Применяем операции (передаем bot для уведомлений)
            result = await user_manager_service.apply_tpoints_changes(file_content, callback.bot)
            
            if result["success"]:
                result_text = (
                    "✅ <b>T-Points операции выполнены!</b>\n\n"
                    f"📊 Обработано операций: {result['applied']}\n"
                )
                
                if result['applied'] > 0:
                    result_text += "\n📬 Уведомления отправлены пользователям."
            else:
                result_text = f"❌ Ошибка при выполнении операций: {result['message']}"
            
            await callback.message.answer(result_text)
            
        except Exception as apply_error:
            logger.error(f"Error applying T-Points operations: {apply_error}")
            await callback.message.answer(f"❌ Ошибка при выполнении операций: {str(apply_error)}")
        finally:
            # Удаляем временный файл через менеджер
            temp_file_manager.remove_file(file_id)
        
        # Возвращаем в меню T-Points
        keyboard = UserManagementKeyboard.get_tpoints_export_menu()
        
        await callback.message.answer(
            text="💎 Управление T-Points",
            reply_markup=keyboard
        )
        
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Critical error confirming T-Points operations: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Произошла критическая ошибка", show_alert=True)


@user_management_router.callback_query(F.data.startswith("users:confirm:"))
async def confirm_users_import(callback: CallbackQuery, user_manager_service: UserManagerService):
    """Подтверждение и применение импорта пользователей"""
    try:
        from ..utils.temp_file_manager import temp_file_manager
        file_id = callback.data.replace("users:confirm:", "")
        file_path = temp_file_manager.get_file_path(file_id)
        
        if not file_path:
            await safe_callback_answer(callback, "❌ Файл не найден или истек срок действия", show_alert=True)
            return
        
        logger.info(f"Confirming users import from file: {file_path}")
        
        if not os.path.exists(file_path):
            temp_file_manager.remove_file(file_id)
            await safe_callback_answer(callback, "❌ Файл не найден", show_alert=True)
            return
        
        # Показываем сообщение о выполнении импорта
        await update_message(
            callback,
            text="⚙️ Выполняем импорт данных сотрудников...",
            reply_markup=None
        )
        
        try:
            # Читаем файл в память
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Применяем импорт
            result = await user_manager_service.import_users_from_excel(file_content)
            
            if result["success"]:
                result_text = (
                    "✅ <b>Импорт сотрудников выполнен!</b>\n\n"
                    f"📊 Обновлено пользователей: {result['updated']}\n"
                )
                
                if result.get('updates') and len(result['updates']) > 0:
                    result_text += "\n<b>📝 Детали обновлений:</b>\n"
                    for update in result['updates'][:3]:
                        result_text += f"• ID {update['telegram_id']}: {list(update['changes'].keys())}\n"
                    
                    if len(result['updates']) > 3:
                        result_text += f"... и ещё {len(result['updates']) - 3} пользователей"
            else:
                result_text = f"❌ Ошибка при импорте: {result['message']}"
                if result.get('errors'):
                    result_text += f"\n\nОшибки:\n" + "\n".join(result['errors'][:3])
            
            await callback.message.answer(result_text)
            
        except Exception as apply_error:
            logger.error(f"Error applying users import: {apply_error}")
            await callback.message.answer(f"❌ Ошибка при выполнении импорта: {str(apply_error)}")
        finally:
            # Удаляем временный файл через менеджер
            temp_file_manager.remove_file(file_id)
        
        # Возвращаем в меню управления пользователями
        keyboard = UserManagementKeyboard.get_users_export_menu()
        
        await callback.message.answer(
            text="👥 Управление сотрудниками",
            reply_markup=keyboard
        )
        
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Critical error confirming users import: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Произошла критическая ошибка", show_alert=True)


@user_management_router.callback_query(F.data.startswith("users:cancel:"))
async def cancel_users_import(callback: CallbackQuery):
    """Отмена импорта пользователей"""
    try:
        from ..utils.temp_file_manager import temp_file_manager
        file_id = callback.data.replace("users:cancel:", "")
        
        # Удаляем временный файл через менеджер
        temp_file_manager.remove_file(file_id)
        
        # Возвращаем в меню управления пользователями
        keyboard = UserManagementKeyboard.get_users_export_menu()
        
        await update_message(
            callback,
            text="❌ Импорт отменен\n\n👥 Управление сотрудниками",
            reply_markup=keyboard
        )
        
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error canceling users import: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Ошибка при отмене", show_alert=True)


@user_management_router.callback_query(F.data.startswith("tpoints:cancel:"))
async def cancel_tpoints_operations(callback: CallbackQuery):
    """Отмена T-Points операций"""
    try:
        from ..utils.temp_file_manager import temp_file_manager
        file_id = callback.data.replace("tpoints:cancel:", "")
        
        # Удаляем временный файл через менеджер
        temp_file_manager.remove_file(file_id)
        
        # Возвращаем в меню T-Points
        keyboard = UserManagementKeyboard.get_tpoints_export_menu()
        
        await update_message(
            callback,
            text="❌ T-Points операции отменены\n\n💎 Управление T-Points",
            reply_markup=keyboard
        )
        
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error canceling T-Points operations: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Ошибка при отмене", show_alert=True)


@user_management_router.callback_query(F.data == "tpoints:journal")
async def export_tpoints_journal(callback: CallbackQuery, user_manager_service: UserManagerService):
    """Экспорт журнала T-Points операций в Excel"""
    try:
        logger.info(f"User {callback.from_user.id} requesting T-Points journal export")
        
        # Показываем сообщение о начале экспорта
        await update_message(
            callback,
            text="📊 Генерируем журнал операций T-Points...",
            reply_markup=None
        )
        
        # Генерируем Excel файл с журналом (за последние 30 дней)
        excel_buffer = await user_manager_service.export_tpoints_journal_to_excel(days=30)
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
            temp_file.write(excel_buffer.getvalue())
            temp_file_path = temp_file.name
        
        # Отправляем файл
        await callback.message.answer_document(
            document=FSInputFile(temp_file_path, filename="tpoints_journal.xlsx"),
            caption=(
                "📊 <b>Журнал T-Points операций</b>\n\n"
                "📅 Период: последние 30 дней\n"
                "📋 Данные разбиты по отделам\n"
                "📊 Включена сводная статистика"
            )
        )
        
        # Удаляем временный файл
        os.remove(temp_file_path)
        
        # Показываем меню с опциями
        keyboard = UserManagementKeyboard.get_tpoints_journal_menu()
        
        await callback.message.answer(
            text="✅ Журнал операций выгружен! Что дальше?",
            reply_markup=keyboard
        )
        
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error exporting T-Points journal: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Ошибка при экспорте журнала", show_alert=True)


# ===== ОБРАБОТЧИКИ HR УВЕДОМЛЕНИЙ =====

@user_management_router.callback_query(F.data == "hr_notification_later")
async def handle_hr_notification_later(callback: CallbackQuery):
    """Обработчик кнопки 'Позже' в HR уведомлениях"""
    try:
        logger.info(f"HR user {callback.from_user.id} postponed employee notification")
        
        # Удаляем сообщение с уведомлением
        await callback.message.delete()
        
        # Отправляем подтверждение
        await callback.answer(
            "⏰ Уведомление отложено. Вы можете обработать сотрудника позже через 'Управление сотрудниками'",
            show_alert=True
        )
        
    except Exception as e:
        logger.error(f"Error handling HR notification later: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Ошибка обработки", show_alert=True) 