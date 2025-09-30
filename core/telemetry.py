"""Телеметрия и отслеживание статистики работы бота."""

from typing import Optional, Tuple
from datetime import datetime


class Telemetry:
    """Класс для хранения телеметрии и диагностической информации."""
    
    def __init__(self):
        self.success_sends: int = 0
        self.failed_sends: int = 0
        self.last_error: Optional[str] = None
        self.last_error_time: Optional[datetime] = None
        
        # Детали последней операции вставки
        self.last_paste_strategy: Optional[str] = None
        
        # Детали последнего копирования
        self.last_copy_method: Optional[str] = None
        self.last_copy_length: int = 0
        self.last_copy_is_echo: bool = False
        
        # Готовность ответа
        self.response_wait_loops: int = 0
        self.response_ready_time: float = 0.0
        self.response_stabilized: bool = False
        self.response_stabilized_by: Optional[str] = None
        
        # UI кнопка
        self.last_ui_button: Optional[str] = None
        self.last_ui_avg_color: Optional[Tuple[int, int, int]] = None
        
        # Визуальная стабилизация
        self.last_visual_region: Optional[Tuple[int, int, int, int]] = None
        
        # Координаты последнего клика
        self.last_click_xy: Optional[Tuple[int, int]] = None
        
        # READY_PIXEL
        self.last_ready_pixel: Optional[dict] = None
        
        # Последняя установка модели
        self.last_model_set: Optional[str] = None
        
        # CPU мониторинг
        self.cpu_quiet_seconds: float = 0.0
        self.cpu_last_total_percent: float = 0.0
    
    def record_success(self):
        """Записать успешную отправку."""
        self.success_sends += 1
    
    def record_failure(self, error: str):
        """Записать неудачную отправку с ошибкой."""
        self.failed_sends += 1
        self.last_error = error
        self.last_error_time = datetime.now()
    
    def to_dict(self) -> dict:
        """Преобразовать телеметрию в словарь для диагностики."""
        return {
            'success_sends': self.success_sends,
            'failed_sends': self.failed_sends,
            'last_error': self.last_error,
            'last_paste_strategy': self.last_paste_strategy,
            'last_copy_method': self.last_copy_method,
            'last_copy_length': self.last_copy_length,
            'last_copy_is_echo': self.last_copy_is_echo,
            'response_wait_loops': self.response_wait_loops,
            'response_ready_time': round(self.response_ready_time, 2),
            'response_stabilized': self.response_stabilized,
            'response_stabilized_by': self.response_stabilized_by,
            'last_ui_button': self.last_ui_button,
            'last_ui_avg_color': self.last_ui_avg_color,
            'last_visual_region': self.last_visual_region,
            'last_click_xy': self.last_click_xy,
            'last_ready_pixel': self.last_ready_pixel,
            'last_model_set': self.last_model_set,
            'cpu_quiet_seconds': round(self.cpu_quiet_seconds, 2),
            'cpu_last_total_percent': round(self.cpu_last_total_percent, 2),
        }
