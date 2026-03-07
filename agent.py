import os

from browser_use import Agent
from browser_use.browser.context import BrowserContext
from browser_use.controller.service import Controller
from llm import get_llm
from context import ContextManager
from recovery import log_stuck

SYSTEM_PROMPT_EXTENSION = """
ПРИНЦИПЫ РАБОТЫ:
1. Смотри на страницу и решай самостоятельно — не следуй заготовленным шагам
2. Используй только те элементы, которые реально видишь. Не придумывай селекторы
3. После каждого действия проверяй факт: изменился ли URL, появился ли новый контент, исчезло
   ли что-то? Если страница не изменилась — действие не сработало, не считай его успехом
4. Выполняй ТОЛЬКО то, что явно попросил пользователь. Не делай лишнего
5. Если нужный элемент не виден — прокрути страницу, только потом делай вывод что его нет
6. Если одно и то же действие не даёт прогресса 2 раза подряд — попробуй другой подход
   Если ввод текста в поле поиска не даёт результата за 2 попытки — используй go_to_url с готовым поисковым URL (пример: site.ru/search?q=запрос)
7. Если застрял 3 раза подряд — вызови ask_human() с конкретным вопросом
8. Любая отправка формы, подтверждение, оплата, удаление — вызови confirm_action() до действия
9. Если задача выполнена — вызови done() с кратким отчётом: что сделано, какой результат

ПРАВИЛО "ПРОЧИТАЙ ПЕРЕД ТЕМ КАК ПИСАТЬ":
Если задача требует создать текст на основе чего-то (документ, профиль, описание, резюме) —
сначала открой эту страницу, дождись загрузки и извлеки содержимое с помощью extract_content.
Используй реально прочитанные данные. Не придумывай и не используй шаблоны.

ПРАВИЛО "ОТКРОЙ ПЕРЕД ТЕМ КАК ДЕЙСТВОВАТЬ":
Прежде чем совершить действие над объектом (подать заявку, отредактировать, удалить) —
открой его страницу и прочитай содержимое. Это нужно чтобы понять контекст и убедиться что
ты работаешь с нужным объектом.

ЯЗЫК — ОБЯЗАТЕЛЬНОЕ ТРЕБОВАНИЕ:
Все поля ответа (Memory, Eval, Next goal, done text) — ИСКЛЮЧИТЕЛЬНО на русском языке.
Английский язык в ответах ЗАПРЕЩЁН. Отвечай по-русски даже если задача на английском.
"""


def create_agent(task: str, controller: Controller, browser_context: BrowserContext) -> Agent:
    llm = get_llm(temperature=0)
    return Agent(
        task=task,
        llm=llm,
        browser_context=browser_context,
        controller=controller,
        tool_calling_method="function_calling",
        extend_system_message=SYSTEM_PROMPT_EXTENSION,
        max_failures=3,
        use_vision=True,
        max_input_tokens=32000,
        enable_memory=False,
    )


def make_step_hooks(ctx: ContextManager):
    """Создаёт on_step_start и on_step_end хуки с привязкой к ContextManager."""

    async def on_step_start(agent: Agent) -> None:
        """Security hook: перехват опасных URL перед каждым шагом."""
        from security import is_destructive_url
        try:
            page = await agent.browser_context.get_current_page()
            current_url = page.url
            if is_destructive_url(current_url):
                print(f'\n{"!" * 50}')
                print("ВНИМАНИЕ: агент находится на потенциально опасной странице:")
                print(f"  {current_url}")
                answer = input("Продолжить работу агента? (да/нет): ").strip().lower()
                print("!" * 50)
                if answer not in ["да", "yes", "y", "д"]:
                    agent.state.stopped = True
        except Exception:
            pass

    async def on_step_end(agent: Agent) -> None:
        """Progress hook: логирование + трекинг в ContextManager."""
        try:
            step = agent.state.n_steps
            result = agent.state.last_result or []
            errors = [r.error for r in result if getattr(r, "error", None)]
            page = await agent.browser_context.get_current_page()
            url = page.url[:60]

            if errors:
                ctx.add_step(f"step_{step}", str(errors[0])[:100], success=False)
                print(f"  [Шаг {step}] ОШИБКА: {str(errors[0])[:80]}")
                if ctx.is_stuck():
                    log_stuck(ctx.task, ctx.error_count, ctx.get_summary())
            else:
                ctx.add_step(f"step_{step}", url, success=True)
                print(f"  [Шаг {step}] OK — {url}")
        except Exception as e:
            print(f"  [hook error: {e}]")

    return on_step_start, on_step_end
