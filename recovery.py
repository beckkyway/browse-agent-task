"""
Паттерн восстановления при ошибках (Recovery).

Когда агент застревает (3 ошибки подряд), этот модуль:
- Логирует ситуацию
- Предлагает агенту альтернативный подход через расширение системного промпта
- Сбрасывает счётчик ошибок для следующей попытки

Фактический recovery выполняется встроенным механизмом browser-use (max_failures=3),
который заставляет LLM переосмыслить подход. Этот модуль добавляет
явное логирование и трекинг через ContextManager.
"""

import logging

logger = logging.getLogger(__name__)


RECOVERY_HINT = """
RECOVERY MODE: Последние несколько попыток не принесли прогресса.
Подумай нестандартно:
- Попробуй другой элемент или другой подход к той же цели
- Если страница не загружается — попробуй перезагрузить или другой URL
- Если элемент не найден — прокрути страницу или поищи через поиск
- Если совсем застрял — вызови ask_human() с конкретным вопросом
"""


def log_stuck(task: str, error_count: int, step_summary: str) -> None:
    """Логирует состояние застревания агента."""
    logger.warning(
        f"Recovery triggered: {error_count} consecutive failures\n"
        f"Task: {task}\n"
        f"Recent steps:\n{step_summary}"
    )
    print(f"\n[Recovery] Агент адаптируется после {error_count} ошибок подряд...")
    print("[Recovery] browser-use автоматически корректирует стратегию...\n")


def get_recovery_system_hint() -> str:
    """Возвращает подсказку для системного промпта при recovery."""
    return RECOVERY_HINT
