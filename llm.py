"""
Инициализация LLM и DOM Sub-agent.

DOM Sub-agent — отдельный лёгкий LLM вызов для анализа конкретного
вопроса про страницу. Главный агент спрашивает "есть ли поле поиска?" —
DOM Sub-agent анализирует DOM и возвращает конкретный ответ с селектором.
"""

import os
from langchain_openai import ChatOpenAI


def get_llm(model: str = "gpt-4o", temperature: float = 0) -> ChatOpenAI:
    """Основной LLM агента с vision."""
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=os.getenv("OPENAI_API_KEY"),
    )


def get_dom_subagent_llm() -> ChatOpenAI:
    """Лёгкий LLM для DOM Sub-agent — анализ конкретных вопросов про страницу."""
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
    )


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
