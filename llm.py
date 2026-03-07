"""
Инициализация LLM и DOM Sub-agent.

Автоматически выбирает провайдера по наличию ключей в .env:
- GOOGLE_API_KEY → Gemini (gemini-2.0-flash) — бесплатный тариф
- OPENAI_API_KEY → GPT-4o — платный, но качественнее
"""

import os


def get_llm(model: str = None, temperature: float = 0):
    """Основной LLM агента с vision.
    Приоритет: OPENROUTER_API_KEY → GOOGLE_API_KEY → OPENAI_API_KEY.
    """
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if openrouter_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model or "google/gemini-2.0-flash-001",
            temperature=temperature,
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
        )
    elif google_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model or "gemini-2.0-flash",
            temperature=temperature,
            google_api_key=google_key,
        )
    elif openai_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model or "gpt-4o",
            temperature=temperature,
            api_key=openai_key,
        )
    else:
        raise ValueError("Не найден ни OPENROUTER_API_KEY, ни GOOGLE_API_KEY, ни OPENAI_API_KEY в .env")


def get_dom_subagent_llm():
    """Лёгкий LLM для DOM Sub-agent — анализ конкретных вопросов про страницу."""
    google_key = os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if google_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0,
            google_api_key=google_key,
        )
    elif openai_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=openai_key,
        )
    else:
        raise ValueError("Не найден ни GOOGLE_API_KEY, ни OPENAI_API_KEY в .env")


async def ask_about_dom(query: str, dom: str) -> str:
    """
    DOM Sub-agent — отвечает на конкретный вопрос про страницу.

    Отдельный LLM вызов с узкой задачей: найти элемент и вернуть селектор.
    Используется для точечных запросов вместо отправки всего DOM главному агенту.

    Пример запроса: "Есть ли на странице поле поиска? Какой у него селектор?"
    """
    llm = get_dom_subagent_llm()
    prompt = (
        f"Вот список элементов на странице:\n{dom}\n\n"
        f"Вопрос: {query}\n\n"
        "Ответь конкретно. Если нашёл нужный элемент — укажи его точный селектор. "
        "Если не нашёл — так и скажи."
    )
    response = await llm.ainvoke(prompt)
    return response.content
