"""
Управление историей шагов агента и сжатие контекста.
Хранит только последние MAX_STEPS_IN_HISTORY шагов — предотвращает переполнение токенов.
"""

MAX_STEPS_IN_HISTORY = 10


class ContextManager:
    def __init__(self, task: str):
        self.task = task
        self.steps: list[dict] = []
        self.error_count = 0

    def add_step(self, action: str, result: str, success: bool) -> None:
        self.steps.append({"action": action, "result": result, "success": success})
        if not success:
            self.error_count += 1
        else:
            self.error_count = 0

        if len(self.steps) > MAX_STEPS_IN_HISTORY:
            self.steps = self.steps[-MAX_STEPS_IN_HISTORY:]

    def get_summary(self) -> str:
        if not self.steps:
            return "Шагов ещё не было."
        lines = []
        for i, step in enumerate(self.steps, 1):
            status = "✓" if step["success"] else "✗"
            result_short = step["result"][:80] + ("..." if len(step["result"]) > 80 else "")
            lines.append(f"{i}. {status} {step['action']} → {result_short}")
        return "\n".join(lines)

    def is_stuck(self) -> bool:
        """Агент застрял если 3 ошибки подряд."""
        return self.error_count >= 3

    def reset_errors(self) -> None:
        self.error_count = 0

    def total_steps(self) -> int:
        return len(self.steps)
