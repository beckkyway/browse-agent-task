DESTRUCTIVE_PATTERNS = [
    'checkout', 'payment', 'purchase', 'buy-now', 'place-order',
    'оплат', 'confirm', 'delete', 'удал', 'remove', 'pay', 'order/submit',
    'vacancy_response', 'applicant/negotiate', 'resume/apply',
]


def is_destructive_url(url: str) -> bool:
    url_lower = url.lower()
    return any(p in url_lower for p in DESTRUCTIVE_PATTERNS)
