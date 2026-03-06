from browser_use.controller.service import Controller
from browser_use.agent.views import ActionResult


def build_controller() -> Controller:
    controller = Controller()

    @controller.registry.action(
        'Спросить пользователя когда агент застрял или нужна дополнительная информация '
        '(логин, пароль, выбор из вариантов)'
    )
    async def ask_human(question: str) -> ActionResult:
        print(f'\n{"=" * 50}')
        print(f'АГЕНТ СПРАШИВАЕТ: {question}')
        answer = input('> ').strip()
        print('=' * 50)
        return ActionResult(extracted_content=f'Пользователь ответил: {answer}', include_in_memory=True)

    @controller.registry.action(
        'Запросить подтверждение пользователя перед потенциально опасным действием: '
        'оплата, удаление данных, отправка формы с личными данными, подтверждение заказа'
    )
    async def confirm_action(action_description: str) -> ActionResult:
        print(f'\n{"!" * 50}')
        print('ВНИМАНИЕ — потенциально опасное действие:')
        print(f'  {action_description}')
        answer = input('Разрешить? (да/нет): ').strip().lower()
        print('!' * 50)
        if answer in ['да', 'yes', 'y', 'д']:
            return ActionResult(
                extracted_content='Пользователь разрешил действие. Продолжай.',
                include_in_memory=True,
            )
        return ActionResult(
            extracted_content='Пользователь ОТКЛОНИЛ действие. Найди другой способ выполнить задачу.',
            error='Действие отклонено пользователем',
            include_in_memory=True,
        )

    return controller
