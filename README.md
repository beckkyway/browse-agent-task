# AI Browser Agent

Автономный AI-агент управляющий браузером. Пользователь вводит задачу текстом — агент сам открывает браузер, кликает, заполняет формы и возвращает результат.

## Установка

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Вставить один из ключей в .env: OPENROUTER_API_KEY, GOOGLE_API_KEY или OPENAI_API_KEY
```

## Запуск

```bash
source venv/bin/activate
python main.py
```

При запуске введите любую задачу — браузер откроется автоматически. После этого войдите в нужные учётки и продолжайте работу. Сессия (cookies) сохраняется автоматически в `browser_profile/session.json` и восстанавливается при следующих запусках.

## Поддерживаемые провайдеры (приоритет)

Агент выбирает провайдер автоматически по наличию ключа в `.env`:

1. **OpenRouter** (`OPENROUTER_API_KEY`) — бесплатные модели, рекомендуется. Получить ключ: https://openrouter.ai/keys
2. **Google Gemini** (`GOOGLE_API_KEY`) — бесплатный тариф
3. **OpenAI** (`OPENAI_API_KEY`) — GPT-4o, платный

По умолчанию используется `google/gemini-2.0-flash-001` через OpenRouter.

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
| `agent.py` | Фабрика `browser_use.Agent` + lifecycle hooks |
| `browser.py` | Создание браузера с persistent sessions через `cookies_file` |
| `llm.py` | Инициализация LLM: OpenRouter / Gemini / OpenAI |
| `context.py` | `ContextManager` — история шагов, сжатие токенов, трекинг ошибок |
| `security.py` | Детекция опасных URL + `is_destructive_url()` |
| `recovery.py` | Логирование recovery + подсказки при застревании |
| `tools.py` | Кастомные инструменты: `ask_human`, `confirm_action` |

## Паттерны

- **Security layer**: двухуровневая защита — при вводе задачи проверяются ключевые слова (`main.py`), при каждом шаге `on_step_start` перехватывает опасные URL (checkout/payment/delete). Агент также инструктирован вызывать `confirm_action()` перед деструктивными действиями.
- **Recovery**: `on_step_end` + `ContextManager` трекают ошибки подряд; `max_failures=3` в агенте заставляет LLM переосмыслить стратегию; `ask_human` — инструмент для запроса помощи у пользователя; `recovery.py` логирует факт застревания.
- **Persistent sessions**: cookies сохраняются в `browser_profile/session.json` через `BrowserContextConfig(cookies_file=...)` и автоматически загружаются при следующем запуске.
