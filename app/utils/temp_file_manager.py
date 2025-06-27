import os
import uuid
import time
import threading
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class TempFileManager:
    """Менеджер временных файлов с короткими идентификаторами для callback_data"""
    
    def __init__(self):
        self._files: Dict[str, Dict] = {}
        self._cleanup_thread = None
        self._lock = threading.Lock()
        self._start_cleanup_thread()
    
    def store_file(self, file_path: str, ttl_minutes: int = 30) -> str:
        """
        Сохраняет путь к файлу с коротким идентификатором
        
        Args:
            file_path: Полный путь к файлу
            ttl_minutes: Время жизни в минутах
            
        Returns:
            str: Короткий идентификатор для callback_data
        """
        file_id = str(uuid.uuid4())[:8]  # 8 символов достаточно
        expiry_time = time.time() + (ttl_minutes * 60)
        
        with self._lock:
            self._files[file_id] = {
                'path': file_path,
                'expiry': expiry_time,
                'created': time.time()
            }
        
        logger.info(f"Stored temporary file: {file_id} -> {file_path}")
        return file_id
    
    def get_file_path(self, file_id: str) -> Optional[str]:
        """
        Получает путь к файлу по идентификатору
        
        Args:
            file_id: Короткий идентификатор
            
        Returns:
            Optional[str]: Путь к файлу или None если не найден/истек
        """
        with self._lock:
            file_info = self._files.get(file_id)
            
            if not file_info:
                return None
            
            # Проверяем срок действия
            if time.time() > file_info['expiry']:
                # Удаляем файл и запись
                self._cleanup_file(file_id, file_info)
                return None
            
            return file_info['path']
    
    def remove_file(self, file_id: str) -> bool:
        """
        Удаляет файл и его запись
        
        Args:
            file_id: Идентификатор файла
            
        Returns:
            bool: True если файл был удален
        """
        with self._lock:
            file_info = self._files.get(file_id)
            if file_info:
                self._cleanup_file(file_id, file_info)
                return True
            return False
    
    def _cleanup_file(self, file_id: str, file_info: Dict):
        """Очищает файл и его запись (должен вызываться под блокировкой)"""
        try:
            file_path = file_info['path']
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Removed temporary file: {file_path}")
        except Exception as e:
            logger.error(f"Error removing file {file_info['path']}: {e}")
        finally:
            self._files.pop(file_id, None)
    
    def _start_cleanup_thread(self):
        """Запускает фоновый поток для очистки истекших файлов"""
        def cleanup_worker():
            while True:
                try:
                    time.sleep(300)  # Проверяем каждые 5 минут
                    self._cleanup_expired_files()
                except Exception as e:
                    logger.error(f"Error in cleanup worker: {e}")
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        logger.info("Started temp file cleanup thread")
    
    def _cleanup_expired_files(self):
        """Очищает истекшие файлы"""
        current_time = time.time()
        expired_files = []
        
        with self._lock:
            for file_id, file_info in list(self._files.items()):
                if current_time > file_info['expiry']:
                    expired_files.append((file_id, file_info))
        
        for file_id, file_info in expired_files:
            with self._lock:
                if file_id in self._files:  # Двойная проверка
                    self._cleanup_file(file_id, file_info)
        
        if expired_files:
            logger.info(f"Cleaned up {len(expired_files)} expired temporary files")

# Глобальный экземпляр менеджера
temp_file_manager = TempFileManager() 