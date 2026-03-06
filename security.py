import logging

logger = logging.getLogger(__name__)

DESTRUCTIVE_PATTERNS = [
    'checkout', 'payment', 'purchase', 'buy-now', 'place-order',
    'оплат', 'confirm', 'delete', 'удал', 'remove', 'pay', 'order/submit',
    'vacancy_response', 'applicant/negotiate', 'resume/apply',
]


def is_destructive_url(url: str) -> bool:
    url_lower = url.lower()
    return any(p in url_lower for p in DESTRUCTIVE_PATTERNS)


async def on_step_start(agent) -> None:
    """Security hook: intercept navigation to dangerous pages."""
    try:
        page = await agent.browser_context.get_current_page()
        current_url = page.url
        if is_destructive_url(current_url):
            print(f'\n{"!" * 50}')
            print('ВНИМАНИЕ: агент находится на потенциально опасной странице:')
            print(f'  {current_url}')
            answer = input('Продолжить работу агента? (да/нет): ').strip().lower()
            print('!' * 50)
            if answer not in ['да', 'yes', 'y', 'д']:
                agent.state.stopped = True
                logger.info('Агент остановлен пользователем через security hook')
    except Exception as e:
        logger.debug(f'on_step_start hook error (ignored): {e}')


async def on_step_end(agent) -> None:
    """Progress logging hook."""
    try:
        step = agent.state.n_steps
        consecutive = agent.state.consecutive_failures
        result = agent.state.last_result or []
        errors = [r.error for r in result if getattr(r, 'error', None)]

        if errors:
            print(f'  [Шаг {step}] ОШИБКА ({consecutive} подряд): {str(errors[0])[:100]}')
            if consecutive >= 2:
                print(f'  [Recovery] Агент адаптируется после {consecutive} ошибок подряд...')
        else:
            try:
                page = await agent.browser_context.get_current_page()
                url = page.url[:60] + ('...' if len(page.url) > 60 else '')
                print(f'  [Шаг {step}] OK — {url}')
            except Exception:
                print(f'  [Шаг {step}] OK')
    except Exception as e:
        logger.debug(f'on_step_end hook error (ignored): {e}')
