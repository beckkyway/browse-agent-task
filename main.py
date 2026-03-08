import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from browser import create_browser
from agent import create_agent, make_step_hooks
from context import ContextManager
from tools import build_controller


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
    task_ru = task + "\n\n[ВАЖНО: все твои ответы, Memory, Eval, Next goal и done text — только на русском языке]"
    agent = create_agent(task_ru, controller, browser_context)
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

    controller = build_controller()
    browser = create_browser()
    browser_context = await browser.new_context()
    print('Введите любую задачу — браузер откроется автоматически.')
    print('После этого вы сможете войти в нужные учётки и работать с агентом.')
    print('Сессия сохраняется и восстанавливается при следующем запуске.')
    print('Введите "выход" для завершения.\n')

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
