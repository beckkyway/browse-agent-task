# AI Browser Agent — Тестовое задание VLR Dev

## Что мы строим

Аналог **Claude in Chrome** (claude.com/chrome) — AI-агент, который автономно управляет браузером.
Пользователь пишет задачу текстом → агент сам открывает браузер, кликает, заполняет формы, навигирует → возвращает результат.

**Ключевое отличие от скриптов:** агент не знает заранее ни одного шага. Он смотрит на страницу и решает сам — как человек.

---

## Жёсткие требования — нельзя нарушать

- Никаких заготовленных шагов ("сначала нажми кнопку входа")
- Никаких хардкодных селекторов (`a[data-qa='vacancy']`)
- Никаких хардкодных URL (`/vacancies`, `/cart`, `/search`)
- Агент сам смотрит на DOM/скриншот и определяет что делать
- Агент сам находит нужные элементы на странице
- Агент сам догадывается где искать нужный раздел

---

## Полный чеклист реализации

### 1. Автоматизация браузера
- [ ] Программное управление браузером (Playwright через browser-use)
- [ ] **Persistent sessions** — пользователь может войти вручную, агент продолжает работу в той же сессии (сохранять cookies/storage между запусками через `storage_state`)
- [ ] Видимый браузер — **не headless**, должно быть видно как агент работает

### 2. Автономный AI-агент
- [ ] Использует Claude или OpenAI с tool calling
- [ ] Принимает решения без участия пользователя
- [ ] Обрабатывает многошаговые задачи с переходами между страницами

### 3. Управление контекстом (критично!)
- [ ] Нельзя отправлять целые веб-страницы в LLM — переполнит контекст
- [ ] Извлекать только интерактивные элементы (кнопки, ссылки, поля)
- [ ] Хранить историю шагов в сжатом текстовом виде
- [ ] Ограничить количество токенов на один запрос (`max_history_items` в browser-use)

### 4. Продвинутые паттерны (минимум один, лучше два)
- [ ] **Обработка ошибок** — агент адаптируется при неудачных действиях (recovery)
- [ ] **Security layer** — спрашивает пользователя перед деструктивными действиями (оплата, удаление)
- [ ] **Sub-agent архитектура** — специализированные агенты для разных задач (опционально, сложнее)

---

## Что реализуем и почему

**Выбираем:** Обработка ошибок (recovery) + Security layer — это два паттерна, оба несложные, закрывают требование "минимум один" с запасом.

**Sub-agent** — пропускаем, это сложнее и не обязательно для MVP.

---

## Стек

- **Python 3.11**
- **Playwright** — автоматизация, persistent sessions через `storage_state`
- **OpenAI GPT-4o** — vision + tool calling (или Anthropic Claude)
- **browser-use** — готовая основа агента
- **python-dotenv**

---

## Архитектура — главный цикл

```
Пользователь: "купи молоко на wildberries"
        ↓
  main.py принимает задачу
        ↓
  agent.py запускает цикл:
  ┌─────────────────────────────────────────┐
  │  1. llm.think(task, history, screenshot)│
  │     REASONING: что вижу, что делать     │
  │     ACTION: следующий инструмент        │
  │                                         │
  │  2. Типичная цепочка после действия:    │
  │     → click/type/goto                   │
  │     → wait(2)                           │
  │     → take_screenshot                   │
  │     → query_dom("что изменилось?")      │
  │       ↑ DOM Sub-agent отвечает на вопрос│
  │                                         │
  │  3. security.check(action)              │  <- security паттерн
  │     → деструктивное? спросить юзера     │
  │                                         │
  │  4. если ошибка → recovery.handle()     │  <- recovery паттерн
  │                                         │
  │  5. context.add_step(action, result)    │
  └──────────────┬──────────────────────────┘
                 ↓ повторять
        action == "done" → структурированный отчёт
```

---

## Структура файлов

```
agent/
├── CLAUDE-TASK.md      # этот файл
├── main.py             # точка входа, интерфейс
├── agent.py            # главный цикл
├── browser.py          # Playwright + persistent sessions
├── llm.py              # вызовы LLM + DOM Sub-agent
├── tools.py            # инструменты для tool calling
├── context.py          # история + сжатие токенов
├── recovery.py         # паттерн 1: восстановление при ошибках
├── security.py         # паттерн 2: защита от деструктивных действий
├── requirements.txt
├── .env.example
└── README.md
```

**Важно про DOM Sub-agent:** `query_dom` — это отдельный LLM вызов внутри `llm.py`.
Главный агент спрашивает *"есть ли поле поиска?"*, DOM Sub-agent анализирует страницу и отвечает с конкретными селекторами.

---

## Детали реализации

### browser.py — с persistent sessions

```python
class BrowserManager:
    SESSION_FILE = "session.json"  # сохранённые cookies

    async def start(self, headless=False):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)

        # Загружаем сохранённую сессию если есть
        if os.path.exists(self.SESSION_FILE):
            self.context = await self.browser.new_context(
                storage_state=self.SESSION_FILE
            )
            print("Сессия восстановлена")
        else:
            self.context = await self.browser.new_context()

        self.page = await self.context.new_page()

    async def save_session(self):
        # Сохраняем cookies и localStorage после работы
        await self.context.storage_state(path=self.SESSION_FILE)

    async def screenshot(self) -> bytes:
        return await self.page.screenshot()

    async def get_dom(self) -> str:
        # Только интерактивные элементы — не весь HTML
        return await self.page.evaluate("""
            () => {
                const elements = document.querySelectorAll(
                    'button, a, input, select, textarea, [role="button"], [onclick]'
                );
                return Array.from(elements).map(el => {
                    const text = el.innerText?.trim() || el.placeholder || el.value || '';
                    const tag = el.tagName.toLowerCase();
                    const id = el.id ? '#' + el.id : '';
                    const cls = el.className ? '.' + el.className.split(' ')[0] : '';
                    return `[${tag}] ${text} | ${id || cls}`;
                }).filter(s => s.length > 8).slice(0, 50).join('\\n');
            }
        """)

    async def click(self, selector: str) -> str:
        try:
            await self.page.click(selector, timeout=5000)
            await self.page.wait_for_load_state("networkidle", timeout=10000)
            new_url = self.page.url
            new_dom = await self.get_dom()
            return f"OK. URL: {new_url}\nНовые элементы: {new_dom[:300]}"
        except Exception as e:
            current_dom = await self.get_dom()
            return f"ОШИБКА: {str(e)}\nДоступные элементы: {current_dom[:300]}"

    async def type(self, selector: str, text: str) -> str:
        try:
            await self.page.fill(selector, text)
            return f"OK. Введено: '{text}'"
        except Exception as e:
            return f"ОШИБКА: {str(e)}"

    async def goto(self, url: str) -> str:
        try:
            await self.page.goto(url, wait_until="networkidle")
            title = await self.page.title()
            dom = await self.get_dom()
            return f"OK. Страница: {title}\nЭлементы: {dom[:300]}"
        except Exception as e:
            return f"ОШИБКА: {str(e)}"

    async def wait(self, seconds: int) -> str:
        await asyncio.sleep(seconds)
        return f"OK. Подождали {seconds} сек."

    async def take_screenshot(self) -> bytes:
        return await self.page.screenshot()

    async def query_dom(self, query: str) -> str:
        """DOM Sub-agent — отвечает на конкретный вопрос про страницу."""
        dom = await self.get_dom()
        response = await llm.ask_about_dom(query=query, dom=dom)
        return response
```

---

### tools.py

```python
TOOLS = [
    {
        "name": "click",
        "description": """Кликнуть по элементу на странице.
Используй ТОЛЬКО селекторы из списка DOM — никогда не придумывай.
Возвращает: новый URL если страница изменилась, или список новых элементов
которые появились после клика (форма, попап, контент).
Если элемент не найден — возвращает ошибку с подсказкой что видно на странице.""",
        "parameters": {
            "selector": "CSS selector — только из предоставленного списка DOM",
            "reason": "Объяснение: что я ожидаю увидеть после клика"
        }
    },
    {
        "name": "type",
        "description": """Ввести текст в поле формы.
Сначала убедись что поле есть в списке DOM. Очищает поле перед вводом.
Возвращает: подтверждение что текст введён, или ошибку если поле не найдено.""",
        "parameters": {
            "selector": "CSS selector поля ввода — только из DOM",
            "text": "Текст для ввода",
            "reason": "Что я ввожу и зачем"
        }
    },
    {
        "name": "goto",
        "description": """Перейти по URL — открыть новую страницу.
Используй когда знаешь точный URL. Для навигации по сайту лучше кликать по ссылкам.
Возвращает: заголовок страницы и первые интерактивные элементы после загрузки.""",
        "parameters": {
            "url": "Полный URL включая https://",
            "reason": "Зачем переходим на эту страницу"
        }
    },
    {
        "name": "scroll",
        "description": """Прокрутить страницу вверх или вниз.
Используй когда нужный элемент не виден — он может быть ниже на странице.
Возвращает: новые элементы которые стали видны после скролла.""",
        "parameters": {
            "direction": "down или up",
            "reason": "Что ищу после скролла"
        }
    },
    {
        "name": "query_dom",
        "description": """Задать умный вопрос про содержимое страницы.
Используй вместо простого get_dom когда нужен конкретный ответ.
Примеры вопросов:
- "Есть ли на странице поле поиска? Какой у него селектор?"
- "Какие хот-доги есть в результатах? Покажи названия и кнопки добавления в корзину"
- "Хот-дог добавлен в корзину? Что показывает счётчик корзины?"
- "Есть ли попап или модальное окно? Что в нём написано?"
Возвращает: конкретный ответ на вопрос с найденными селекторами.""",
        "parameters": {
            "query": "Конкретный вопрос про страницу — что ищем и что хотим узнать"
        }
    },
    {
        "name": "wait",
        "description": """Подождать несколько секунд.
Используй после клика или перехода — страница может грузиться.
Используй после ввода текста в поиск — результаты появляются с задержкой.""",
        "parameters": {
            "seconds": "Количество секунд (обычно 1-3)"
        }
    },
    {
        "name": "done",
        "description": """Задача полностью выполнена.
Вызывай только когда уверен что достиг цели пользователя.
Возвращает финальный ответ пользователю.""",
        "parameters": {
            "result": "Подробный результат: что сделано, что найдено, конкретные данные"
        }
    },
    {
        "name": "ask_user",
        "description": """Запросить информацию у пользователя.
Вызывай когда застрял и нужны данные которых нет (логин, пароль, выбор из вариантов).
Не злоупотребляй — сначала попробуй решить самостоятельно.""",
        "parameters": {
            "question": "Конкретный вопрос пользователю"
        }
    }
]
```

---

### context.py — управление токенами

```python
class ContextManager:
    MAX_STEPS_IN_HISTORY = 10  # хранить только последние 10 шагов

    def __init__(self, task: str):
        self.task = task
        self.steps: list[dict] = []
        self.error_count = 0

    def add_step(self, action: str, result: str, success: bool):
        self.steps.append({
            "action": action,
            "result": result,
            "success": success
        })
        if not success:
            self.error_count += 1
        else:
            self.error_count = 0

        if len(self.steps) > self.MAX_STEPS_IN_HISTORY:
            self.steps = self.steps[-self.MAX_STEPS_IN_HISTORY:]

    def get_summary(self) -> str:
        if not self.steps:
            return "Только начали, шагов ещё не было."
        lines = []
        for i, step in enumerate(self.steps, 1):
            status = "✓" if step["success"] else "✗"
            lines.append(f"{i}. {status} {step['action']} → {step['result']}")
        return "\n".join(lines)

    def is_stuck(self) -> bool:
        return self.error_count >= 3

    def reset_errors(self):
        self.error_count = 0
```

---

### security.py — защита деструктивных действий

```python
DESTRUCTIVE_KEYWORDS = [
    "оплат", "купить", "заказ", "checkout", "payment", "purchase",
    "удал", "delete", "remove", "отправ", "send", "submit",
    "подтверд", "confirm", "agree"
]

class SecurityLayer:
    def is_destructive(self, action_name: str, action_args: dict) -> bool:
        if action_name not in ["click", "goto"]:
            return False

        text_to_check = " ".join([
            action_args.get("reason", ""),
            action_args.get("selector", ""),
            action_args.get("url", "")
        ]).lower()

        return any(kw in text_to_check for kw in DESTRUCTIVE_KEYWORDS)

    def confirm(self, action_name: str, action_args: dict) -> bool:
        print(f"\nВНИМАНИЕ — потенциально опасное действие:")
        print(f"   Действие: {action_name}")
        print(f"   Причина: {action_args.get('reason', '—')}")
        answer = input("   Разрешить? (да/нет): ").strip().lower()
        return answer in ["да", "yes", "y", "д"]
```

---

### recovery.py — восстановление при ошибках

```python
async def handle(ctx: ContextManager, browser: BrowserManager, llm) -> dict:
    print(f"\nЗастрял ({ctx.error_count} ошибки подряд). Пробую другой подход...")

    screenshot = await browser.screenshot()
    dom = await browser.get_dom()

    recovery_prompt = f"""
Задача: {ctx.task}

История (последние шаги провалились):
{ctx.get_summary()}

Текущая страница: {await browser.get_url()}
Элементы на странице:
{dom}

Последние 3 действия не дали прогресса.
Предложи ДРУГОЙ подход — попробуй другой селектор, другой путь к цели,
или спроси пользователя если совсем не понятно как продолжить.
"""

    action = await llm.think_with_prompt(recovery_prompt, screenshot)
    ctx.reset_errors()
    return action
```

---

### llm.py — системный промпт и DOM Sub-agent

```python
SYSTEM_PROMPT = """
На каждом шаге тебе дают:
- Задачу пользователя
- Краткую историю уже выполненных шагов
- Скриншот текущей страницы
- Список интерактивных элементов с их CSS-селекторами

ОБЯЗАТЕЛЬНЫЙ ФОРМАТ ОТВЕТА — всегда перед действием пиши:

REASONING: [что я вижу на странице, какой прогресс сделан, почему выбираю именно это действие]
ACTION: [вызов инструмента]

ПОРЯДОК РАБОТЫ НА КАЖДОМ ШАГЕ:
1. Сделал действие (click/type/goto)
2. Вызвал wait(2) — дать странице загрузиться
3. Вызвал take_screenshot — посмотреть что изменилось
4. Вызвал query_dom с конкретным вопросом — уточнить детали
5. Принял решение о следующем шаге

ПРАВИЛА:
1. Всегда используй query_dom с конкретным вопросом вместо простого дампа DOM
   Плохо: "покажи все элементы"
   Хорошо: "есть ли кнопка добавить в корзину? какой у неё селектор?"
2. Используй ТОЛЬКО селекторы которые вернул query_dom — никогда не придумывай
3. После каждого действия жди (wait) и делай скриншот
4. Если задача выполнена — вызови done() со структурированным отчётом
5. Если не можешь продолжить 3 раза подряд — вызови ask_user()
6. Действуй как человек: сначала открой сайт, найди нужный раздел, выполни задачу
7. Оценивай прогресс — двигаешься ли ты к цели?

ФОРМАТ ФИНАЛЬНОГО ОТЧЁТА в done():
Шаг 1 — что сделано
Шаг 2 — что сделано
Шаг 3 — что сделано

[Итог и важные детали: цены, названия, количества]
"""

async def think(task, history, screenshot, dom) -> dict:
    """Главный агент — решает что делать дальше"""
    ...

async def ask_about_dom(query: str, dom: str) -> str:
    """DOM Sub-agent — отвечает на конкретный вопрос про страницу.
    Отдельный LLM вызов с узкой задачей: найти элемент и вернуть селектор.
    """
    prompt = f"""
Вот список элементов на странице:
{dom}

Вопрос: {query}

Ответь конкретно. Если нашёл нужный элемент — укажи его точный селектор.
Если не нашёл — так и скажи.
"""
    response = await llm_call(prompt)
    return response
```

---

### agent.py — главный цикл со всеми паттернами

```python
async def run(task: str, browser: BrowserManager) -> str:
    ctx = ContextManager(task)
    sec = SecurityLayer()

    for step in range(MAX_STEPS):
        screenshot = await browser.screenshot()
        dom = await browser.get_dom()

        # Recovery если застряли
        if ctx.is_stuck():
            action = await recovery.handle(ctx, browser, llm)
        else:
            action = await llm.think(task, ctx.get_summary(), screenshot, dom)

        if action["name"] == "done":
            await browser.save_session()
            return action["args"]["result"]

        if action["name"] == "ask_user":
            answer = input(f"\n{action['args']['question']}\n> ")
            ctx.add_step("ask_user", answer, success=True)
            continue

        # Security check перед деструктивным действием
        if sec.is_destructive(action["name"], action["args"]):
            if not sec.confirm(action["name"], action["args"]):
                ctx.add_step(str(action), "отклонено пользователем", success=False)
                continue

        success = await browser.execute(action)
        ctx.add_step(
            f"{action['name']}({action['args'].get('reason', '')})",
            "ok" if success else "failed",
            success=success
        )

    return "Превышен лимит шагов"
```

---

### main.py

```python
async def main():
    print("=" * 50)
    print("  AI Browser Agent")
    print("=" * 50)

    browser = BrowserManager()
    await browser.start(headless=False)

    if not os.path.exists("session.json"):
        print("\nСессия не найдена.")
        print("Войдите вручную в браузере на нужный сайт, затем нажмите Enter...")
        input()
        await browser.save_session()
        print("Сессия сохранена!\n")
    else:
        print("Сессия восстановлена автоматически\n")

    print("Введите задачу (или 'выход'):")
    while True:
        task = input("\n> ").strip()
        if task.lower() in ["выход", "exit"]:
            break
        if not task:
            continue
        print("\nЗапускаю агента...")
        result = await agent.run(task, browser)
        print(f"\nРезультат:\n{result}\n")
        print("-" * 50)

    await browser.save_session()
    await browser.close()
```

---

## browser-use API — справочник

### Быстрый старт с browser-use

```python
from browser_use import Agent, Browser, ChatBrowserUse

browser = Browser(
    headless=False,              # показываем браузер
    window_size={'width': 1280, 'height': 720},
    storage_state='session.json',  # persistent sessions
)

agent = Agent(
    task="Find top Python vacancies",
    browser=browser,
    llm=ChatBrowserUse(),
    max_failures=3,              # recovery: макс попыток перед ошибкой
    max_history_items=10,        # контекст: хранить только 10 шагов
    use_vision=True,             # vision: видит скриншот
)

history = await agent.run(max_steps=50)
print(history.final_result())
```

### Ключевые параметры агента

| Параметр | По умолчанию | Описание |
|---|---|---|
| `max_failures` | `3` | Макс ретраев при ошибках (recovery) |
| `final_response_after_failure` | `True` | Финальный ответ после исчерпания попыток |
| `use_vision` | `"auto"` | Vision режим — `True` всегда включён |
| `max_history_items` | `None` | Лимит шагов в памяти LLM |
| `use_thinking` | `True` | Внутренние рассуждения агента |
| `override_system_message` | — | Заменить системный промпт |
| `extend_system_message` | — | Добавить к системному промпту |
| `save_conversation_path` | — | Путь для сохранения истории |

### Ключевые параметры браузера

| Параметр | По умолчанию | Описание |
|---|---|---|
| `headless` | `None` | `False` = видимый браузер |
| `storage_state` | — | Путь к файлу сессии (cookies + localStorage) |
| `user_data_dir` | авто | Директория профиля браузера |
| `wait_between_actions` | `0.5` | Пауза между действиями агента |
| `minimum_wait_page_load_time` | `0.25` | Минимальное ожидание загрузки страницы |
| `highlight_elements` | `True` | Подсвечивать элементы для AI vision |

### Persistent sessions (два способа)

**Способ 1 — storage_state (рекомендуется):**
```python
# Экспорт из реального браузера
browser = Browser.from_system_chrome()
await browser.start()
await browser.export_storage_state('session.json')
await browser.stop()

# Загрузка в headless/headful режиме
browser = Browser(storage_state='session.json')
# Файл автоматически обновляется при каждом запуске
```

**Способ 2 — реальный Chrome профиль:**
```python
# Подключение к вашему Chrome (уже авторизованному)
browser = Browser.from_system_chrome()
# или с конкретным профилем:
browser = Browser.from_system_chrome(profile_directory='Profile 1')
```

### Lifecycle hooks — для security паттерна

```python
async def security_hook(agent: Agent):
    """Вызывается перед каждым шагом — можно перехватить опасные действия"""
    state = await agent.browser_session.get_browser_state_summary()
    current_url = state.url
    # Проверяем URL на опасные паттерны (checkout, payment, etc.)
    if any(kw in current_url for kw in ['checkout', 'payment', 'confirm']):
        answer = input(f"Агент собирается перейти на {current_url}. Разрешить? (да/нет): ")
        if answer.lower() not in ['да', 'yes', 'y']:
            agent.pause()

await agent.run(on_step_start=security_hook, max_steps=50)
```

### Кастомные инструменты (security + recovery через Tools)

```python
from browser_use import Tools, ActionResult, BrowserSession

tools = Tools()

@tools.action(description='Запросить подтверждение у пользователя перед опасным действием')
async def confirm_action(action_description: str) -> ActionResult:
    print(f"\nВНИМАНИЕ: {action_description}")
    answer = input("Разрешить? (да/нет): ").strip().lower()
    if answer in ['да', 'yes', 'y']:
        return ActionResult(extracted_content="Пользователь разрешил действие")
    return ActionResult(extracted_content="Пользователь отклонил действие")

@tools.action(description='Спросить пользователя когда агент застрял')
async def ask_human(question: str) -> ActionResult:
    answer = input(f'{question}\n> ')
    return ActionResult(extracted_content=f'Пользователь ответил: {answer}')

agent = Agent(task="...", llm=llm, tools=tools)
```

### Доступные встроенные инструменты browser-use

| Инструмент | Описание |
|---|---|
| `search` | Поиск через DuckDuckGo/Google/Bing |
| `navigate` | Переход по URL |
| `click` | Клик по элементу по индексу |
| `input` | Ввод текста в форму |
| `scroll` | Прокрутка страницы |
| `find_text` | Скролл до текста |
| `send_keys` | Спецклавиши (Enter, Tab, Escape) |
| `extract` | Извлечение данных через LLM |
| `screenshot` | Скриншот страницы |
| `go_back` | Назад в истории браузера |
| `evaluate` | Выполнить JavaScript |
| `done` | Завершить задачу |

### Результат выполнения

```python
history = await agent.run()

history.final_result()         # финальный ответ агента
history.urls()                 # посещённые URL
history.extracted_content()    # извлечённый контент
history.errors()               # ошибки (None для успешных шагов)
history.is_done()              # завершён ли агент
history.has_errors()           # были ли ошибки
history.number_of_steps()      # количество шагов
history.model_thoughts()       # рассуждения агента
```

---

## Установка и запуск

```bash
git clone <repo>
cd agent
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# вставить API ключи в .env
python main.py
```

---

## requirements.txt

```
playwright==1.44.0
openai==1.30.0
anthropic==0.28.0
browser-use==0.1.40
langchain-openai==0.1.8
python-dotenv==1.0.0
pillow==10.3.0
```

---

## .env.example

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MAX_STEPS=50
```

---

## Тестовые задачи для демо-видео

**Простые (отладка):**
- "открой google.com и найди погоду в Москве"
- "зайди на github.com/trending и назови топ-3 репозитория"

**Сложные (для видео):**
- "зайди на hh.ru, найди топ-3 вакансии Python-разработчика в Москве от 200к"
- "зайди на wildberries.ru, найди самые дешёвые наушники с рейтингом выше 4.5"
- "открой habr.com и найди 3 последние статьи про AI-агентов"

**С security layer (для демонстрации паттерна):**
- "зайди в gmail и удали все письма от рассылок" — агент должен спросить подтверждение

---

## Критерии оценки

- **Умение искать** — нашёл нужные библиотеки, разобрался в API
- **Архитектурное мышление** — понятная структура, разделение ответственности
- **Работа с AI** — грамотно использовал Claude Code / ChatGPT в разработке
- **Практика** — агент реально работает и решает задачи

---

## Пример живой сессии агента

```
> открой яндекс лавку, выбери рабочий адрес доставки и найди хот-дог, добавь в корзину

Открываю Яндекс Лавку и помогу найти хот-дог!

REASONING: Начинаю с открытия главной страницы. Адрес доставки уже сохранён в сессии.
ACTION: goto("https://lavka.yandex.ru")

Using tool: navigate_to_url
  Input: {"url": "https://lavka.yandex.ru"}
  Result: Successfully navigated to https://lavka.yandex.ru

Using tool: wait
  Input: {"seconds": 2}

Using tool: take_screenshot

Using tool: query_dom
  Input: {"query": "Есть ли на странице кнопка адреса доставки? Что там отображается?"}
  DOM Sub-agent: Да, кнопка с адресом доставки '.content__address__vq2eo' показывает
  текущий адрес с иконкой геолокации.

REASONING: Вижу кнопку адреса. Кликаю чтобы выбрать рабочий адрес.
ACTION: click(".content__address__vq2eo")

Using tool: query_dom
  Input: {"query": "Появился ли список сохранённых адресов? Есть ли адрес Работа?"}
  DOM Sub-agent: Да, открылся попап. Есть адреса: Дом, Работа. Селектор: '.address-item__work'

Using tool: click_element
  Input: {"selector": ".address-item__work", "reason": "выбрать адрес Работа"}

Using tool: query_dom
  Input: {"query": "Есть ли на странице поле поиска? Какой у него селектор?"}
  DOM Sub-agent: Да, есть поле поиска. Селектор: '#search-input-id'

Using tool: type_text
  Input: {"selector": "#search-input-id", "text": "хот-дог"}

Using tool: query_dom
  Input: {"query": "Какие хот-доги появились в результатах? Покажи кнопки добавления в корзину"}
  DOM Sub-agent: Найдено 3 результата:
  1. Хот-дог Датский 135г — 279р | кнопка: '.button__add--item1'
  2. Хот-дог Французский 115г — 249р | кнопка: '.button__add--item2'

REASONING: Вижу хот-доги. Добавляю первый.
ACTION: click('.button__add--item1')

Using tool: query_dom
  Input: {"query": "Хот-дог добавлен в корзину? Что показывает счётчик корзины?"}
  DOM Sub-agent: Да, добавлен. Корзина показывает "1 товар • 279р"

Выполнено:
Выбран рабочий адрес доставки "Работа"
Найден хот-дог "Датский 135г" (279р)
Добавлен в корзину (1 шт.)
```
