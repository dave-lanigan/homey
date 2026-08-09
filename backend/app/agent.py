import os
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

def create_agent() -> Agent:
    model = OpenAIModel(
        os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    return Agent(
        model,
        system_prompt=(
            "You are Homey, a friendly AI assistant that helps users filter through "
            "Airbnb listings and find the perfect home. "
            "Ask clarifying questions about location, budget, dates, amenities, and "
            "the number of guests to narrow down the best options. "
            "Be concise, helpful, and enthusiastic about travel."
        ),
    )

agent = create_agent()
