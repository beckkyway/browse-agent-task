from browser_use.controller.service import Controller
from browser_use.agent.views import ActionResult
from browser_use.browser.context import BrowserSession
from llm import ask_about_dom


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

    @controller.registry.action(
        'Задать конкретный вопрос про элементы на текущей странице. '
        'Используй когда нужно найти элемент, проверить наличие кнопки или поля, '
        'не загружая весь DOM в основной контекст.'
    )
    async def ask_dom(question: str, browser: BrowserSession) -> ActionResult:
        page = await browser.get_current_page()
        dom = await page.evaluate('() => document.body.innerText')
        answer = await ask_about_dom(question, dom[:8000])
        return ActionResult(extracted_content=answer, include_in_memory=True)

    @controller.registry.action(
        'Проверить что товар добавлен в корзину и убедиться что не добавлен лишний товар. '
        'Вызывай ПОСЛЕ каждого клика на кнопку добавления в корзину.'
    )
    async def verify_cart(product_name: str, browser: BrowserSession) -> ActionResult:
        page = await browser.get_current_page()
        result = await page.evaluate("""
            () => {
                const lines = [];

                // 1. Счётчик корзины в шапке
                const cartCounterSelectors = [
                    '[class*="cart"][class*="count"]',
                    '[class*="basket"][class*="count"]',
                    '[class*="CartButton"]',
                    '[data-testid*="cart"]',
                    '[class*="cartBadge"]',
                    '[class*="cart-badge"]',
                ];
                for (const sel of cartCounterSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.textContent.trim() && el.textContent.trim() !== '0') {
                        lines.push('Счётчик корзины: ' + el.textContent.trim());
                        break;
                    }
                }

                // 2. Ищем кнопки '-' на странице (признак добавленных товаров)
                const allButtons = Array.from(document.querySelectorAll('button, [role="button"]'));
                const minusBtns = allButtons.filter(b =>
                    b.textContent.trim() === '-' ||
                    b.getAttribute('aria-label')?.toLowerCase().includes('minus') ||
                    b.getAttribute('aria-label')?.toLowerCase().includes('убрать') ||
                    b.getAttribute('aria-label')?.toLowerCase().includes('уменьш') ||
                    b.getAttribute('data-testid')?.toLowerCase().includes('minus') ||
                    b.getAttribute('data-testid')?.toLowerCase().includes('remove')
                );
                lines.push('Кнопок "-" на странице: ' + minusBtns.length);

                // 3. Ищем товары со счётчиком количества (поле с числом между "+" и "-")
                const spinners = Array.from(document.querySelectorAll(
                    '[class*="spin"] [class*="count"], [class*="counter"], [data-testid*="count"]'
                )).filter(el => /^[1-9]/.test(el.textContent.trim()));
                if (spinners.length > 0) {
                    lines.push('Товары с ненулевым счётчиком: ' + spinners.map(e => {
                        // Попытка найти название товара рядом
                        const card = e.closest('[class*="product"], [class*="item"], [class*="card"], li, article');
                        const title = card ? (card.querySelector('[class*="name"], [class*="title"], h2, h3')?.textContent?.trim() || '') : '';
                        return (title ? title + ' × ' : '') + e.textContent.trim();
                    }).join('; '));
                }

                if (lines.length === 0) return 'НЕ ПОДТВЕРЖДЕНО: признаков добавления не найдено. Попробуй hover на карточку товара.';
                return 'ДОБАВЛЕН: ' + lines.join(' | ');
            }
        """)
        return ActionResult(extracted_content=result, include_in_memory=True)

    return controller
