# AI Browser Agent

Автономный AI-агент управляющий браузером. Пользователь вводит задачу текстом — агент сам открывает браузер, кликает, заполняет формы и возвращает результат.

## Установка

```bash
cd agent
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Вставить OPENAI_API_KEY (или OPENROUTER_API_KEY / GOOGLE_API_KEY) в .env
```

## Запуск

```bash
python main.py
```

При первом запуске откроется браузер — войдите на нужные сайты вручную, затем нажмите Enter. Сессия сохранится в `browser_profile/session.json` и будет автоматически восстанавливаться при следующих запусках.

## Поддерживаемые модели

Агент работает с любой моделью через LangChain:
- **OpenAI** — GPT-4o, GPT-4o-mini (основная конфигурация)
- **OpenRouter** — бесплатные и платные модели (укажи `OPENROUTER_API_KEY`)
- **Google Gemini** — через `langchain-google-genai` (укажи `GOOGLE_API_KEY`)

Один запрос потребляет в среднем **30 000 – 50 000 токенов** в зависимости от сложности задачи.

## Использование

```
> открой google.com и найди погоду в Москве
> зайди на hh.ru, найди подходящие вакансии и откликнись с сопроводительным письмом
> зайди на lavka.yandex.ru и добавь в корзину самый дешёвый хот-дог
> открой habr.com и найди 3 последние статьи про AI-агентов
```

Введите `выход` для завершения.

## Архитектура

| Файл | Описание |
|------|----------|
| `main.py` | Точка входа, REPL-цикл, управление сессией |
| `agent.py` | Фабрика `browser_use.Agent` с GPT-4o + lifecycle hooks |
| `browser.py` | `BrowserManager` с persistent sessions через `cookies_file` |
| `llm.py` | Инициализация LLM и DOM Sub-agent (GPT-4o / GPT-4o-mini) |
| `context.py` | `ContextManager` — история шагов, сжатие токенов, трекинг ошибок |
| `security.py` | Детекция опасных URL + `is_destructive_url()` |
| `recovery.py` | Логирование recovery + подсказки при застревании |
| `tools.py` | Кастомные инструменты: `ask_human`, `confirm_action` |

## Паттерны

- **Security layer**: двухуровневая защита — при вводе задачи проверяются ключевые слова (`main.py`), при каждом шаге `on_step_start` перехватывает опасные URL (checkout/payment/delete). Агент также инструктирован вызывать `confirm_action()` перед деструктивными действиями.
- **Recovery**: `on_step_end` + `ContextManager` трекают ошибки подряд; `max_failures=3` в агенте заставляет LLM переосмыслить стратегию; `ask_human` — инструмент для запроса помощи у пользователя; `recovery.py` логирует факт застревания.
- **Persistent sessions**: cookies сохраняются в `browser_profile/session.json` через `BrowserContextConfig(cookies_file=...)` и автоматически загружаются при следующем запуске.
