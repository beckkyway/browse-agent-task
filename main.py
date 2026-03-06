import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from browser import SESSION_FILE, create_browser
from agent import create_agent, make_step_hooks
from context import ContextManager
from tools import build_controller


async def save_session_via_login() -> None:
    """Open browser for manual login, then save session to SESSION_FILE."""
    import json
    from playwright.async_api import async_playwright

    print('\nСессия не найдена. Открываю браузер для входа...')
    print('Войдите на нужные сайты, затем нажмите Enter в этом терминале.')

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto('about:blank')
        input('\nНажмите Enter когда закончите вход...')
        # browser-use cookies_file expects a plain cookies array, not storage_state dict
        cookies = await context.cookies()
        with open(SESSION_FILE, 'w') as f:
            json.dump(cookies, f)
        await browser.close()

    print(f'Сессия сохранена: {SESSION_FILE}\n')


DESTRUCTIVE_TASK_KEYWORDS = [
    'удали', 'удалить', 'удаление', 'delete', 'remove',
    'оплати', 'оплатить', 'оплата', 'купи', 'купить', 'pay', 'purchase',
    'отправь', 'отправить', 'send', 'submit',
    'подтверди', 'подтвердить', 'confirm',
    'откликн', 'отклик', 'apply', 'отправь резюме',
]


def is_destructive_task(task: str) -> bool:
    task_lower = task.lower()
    return any(kw in task_lower for kw in DESTRUCTIVE_TASK_KEYWORDS)


async def run_task(task: str, controller, browser_context) -> None:
    if is_destructive_task(task):
        print(f'\n{"!" * 50}')
        print('ВНИМАНИЕ — задача содержит потенциально опасное действие:')
        print(f'  {task}')
        answer = input('Запустить агента? (да/нет): ').strip().lower()
        print('!' * 50)
        if answer not in ['да', 'yes', 'y', 'д']:
            print('Задача отменена.')
            return

    ctx = ContextManager(task)
    agent = create_agent(task, controller, browser_context)
    on_step_start, on_step_end = make_step_hooks(ctx)
    max_steps = int(os.getenv('MAX_STEPS', '50'))
    history = await agent.run(
        max_steps=max_steps,
        on_step_start=on_step_start,
        on_step_end=on_step_end,
    )
    print('\n' + '=' * 60)
    print('РЕЗУЛЬТАТ:')
    result = history.final_result()
    print(result if result else 'Агент не вернул финальный результат')
    print(f'\nШагов выполнено: {history.number_of_steps()}')
    errors = [e for e in history.errors() if e]
    if errors:
        print(f'Ошибок: {len(errors)}')
    print('=' * 60)


async def main() -> None:
    os.makedirs('browser_profile', exist_ok=True)

    if not os.path.exists(SESSION_FILE):
        await save_session_via_login()

    controller = build_controller()
    browser = create_browser()
    browser_context = await browser.new_context()
    print('Браузер запущен. Введите задачу или "выход" для завершения.\n')

    first_task = ' '.join(sys.argv[1:]).strip()

    try:
        if first_task:
            print(f'Задача: {first_task}')
            print('=' * 60)
            await run_task(first_task, controller, browser_context)

        while True:
            try:
                task = input('\n> ').strip()
            except EOFError:
                break
            if not task:
                continue
            if task.lower() in ('выход', 'exit', 'quit'):
                break
            print('=' * 60)
            await run_task(task, controller, browser_context)
    finally:
        await browser.close()
        print('Браузер закрыт.')


if __name__ == '__main__':
    asyncio.run(main())
