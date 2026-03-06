import os

from browser_use import Agent
from browser_use.browser.context import BrowserContext
from browser_use.controller.service import Controller
from llm import get_llm
from context import ContextManager
from recovery import log_stuck

SYSTEM_PROMPT_EXTENSION = """
ЯЗЫК: Все твои рассуждения, выводы, объяснения и финальный отчёт пиши ТОЛЬКО на русском языке.
Это касается ВСЕХ полей: Eval, Memory, Next goal, рассуждений перед действием — всё на русском.

ОБЯЗАТЕЛЬНЫЙ ФОРМАТ ОТВЕТА на каждом шаге:
РАССУЖДЕНИЕ: [что вижу на странице, какой прогресс сделан, почему выбираю именно это действие]
ДЕЙСТВИЕ: [вызов инструмента]

ПРАВИЛА:
1. Действуй как человек: сначала открой сайт, найди нужный раздел, выполни задачу
2. Используй только те элементы, которые реально видишь на странице
3. После каждого действия оценивай: двигаешься ли ты к цели?
4. Если задача выполнена — вызови done() со структурированным отчётом на русском
5. Если застрял 3 раза подряд — вызови ask_human() с конкретным вопросом
6. Перед опасными действиями (оплата, удаление, подтверждение заказа) — вызови confirm_action()
7. Никогда не придумывай селекторы — используй только то что видишь
8. На e-commerce сайтах (Лавка, WB, Ozon) кнопка "+" часто появляется только при наведении на карточку товара — сначала наведи мышь (hover) на карточку, потом кликай кнопку добавления в корзину
9. Если одно и то же действие (тот же элемент, тот же индекс) не дало нового результата 2 раза подряд — СТОП. Попробуй другой элемент, другой подход или вызови ask_human()
10. Выполняй ТОЛЬКО то, что явно попросил пользователь. Если задача "добавь в корзину" — добавь товар и вызови done(). НЕ переходи к оформлению заказа, оплате или следующим шагам если это не было запрошено
11. ПРОВЕРКА ЦЕНЫ: если в задаче есть ценовое условие (например, "только если дешевле 100р"):
    - Используй extract_content чтобы получить список товаров с их точными ценами
    - Найди ОДИН товар у которого название максимально точно совпадает с запросом И цена соответствует условию
    - Только после этого нажимай "+" именно для этого товара — строго ОДИН раз
    - Если ни один товар не подходит — НЕ добавляй ничего, сообщи в done() что условие не выполнено
    - В финальном отчёте укажи реальную цену и название добавленного товара
12. ПОИСК ЧЕРЕЗ URL: если ввод текста в поле поиска не работает — используй navigate с поисковым запросом через адресную строку браузера (поищи на странице как устроен URL поиска и повтори паттерн)
13. ПРОВЕРКА ПОСЛЕ ДОБАВЛЕНИЯ В КОРЗИНУ: после клика на "+" используй extract_content чтобы убедиться что товар появился в корзине (счётчик увеличился). Только после подтверждения считай шаг выполненным
14. МОДАЛЬНЫЕ ОКНА: если на странице появился попап или модальное окно не связанное с задачей — сразу закрой его (кнопка X или ESC) прежде чем продолжать
15. МНОГОЗАДАЧНЫЕ ЗАПРОСЫ: если в задаче несколько пунктов — перед вызовом done() явно проверь каждый пункт по списку. Вызывай done() только когда все пункты выполнены или обоснованно пропущены
16. ЭЛЕМЕНТ НЕ НАЙДЕН: если нужный элемент не виден на странице — сначала прокрути страницу вниз, только потом делай вывод что элемента нет
17. ПРОВЕРКА НАЗВАНИЯ ТОВАРА: перед тем как добавить ЛЮБОЙ товар в корзину — обязательно вызови extract_content чтобы получить список товаров с названиями на текущей странице. Убедись что в списке есть товар с нужным названием. Только после этого кликай кнопку "+" именно для этого товара. Никогда не кликай наугад по индексу основываясь только на скриншоте

ФОРМАТ ФИНАЛЬНОГО ОТЧЁТА в done():
Шаг 1 — что сделано
Шаг 2 — что сделано
...
[Итог и важные данные: цены, названия, количества]
"""


def create_agent(task: str, controller: Controller, browser_context: BrowserContext) -> Agent:
    llm = get_llm(model="gpt-4o", temperature=0)
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
            consecutive = agent.state.consecutive_failures
            result = agent.state.last_result or []
            errors = [r.error for r in result if getattr(r, "error", None)]

            if errors:
                ctx.add_step(f"step_{step}", str(errors[0])[:100], success=False)
                print(f"  [Шаг {step}] ОШИБКА ({consecutive} подряд): {str(errors[0])[:100]}")
                if ctx.is_stuck():
                    log_stuck(ctx.task, ctx.error_count, ctx.get_summary())
            else:
                try:
                    page = await agent.browser_context.get_current_page()
                    url = page.url
                    ctx.add_step(f"step_{step}", url[:80], success=True)
                    url_short = url[:60] + ("..." if len(url) > 60 else "")
                    print(f"  [Шаг {step}] OK — {url_short}")
                except Exception:
                    ctx.add_step(f"step_{step}", "ok", success=True)
                    print(f"  [Шаг {step}] OK")
        except Exception:
            pass

    return on_step_start, on_step_end
