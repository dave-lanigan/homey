import os
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from dotenv import load_dotenv

from api.tools.agent_search import smart_search_listings_tool
from api.tools.filter import AirbnbFilters, filter_listings_tool, update_search_filters_tool

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

MODEL = "gemini-2.5-flash"

provider = GoogleProvider(api_key=os.getenv("GOOGLE_API_KEY"))
model = GoogleModel(MODEL, provider=provider)


agent = Agent(
    model,
    description=(
        "An AI assistant that helps users find Airbnb listings"
        "based on their search criteria and natural language requests."
    ),
    system_prompt=(
        "You are Homey, a friendly AI assistant that helps users find Airbnb listings.",
        "Your goal is to overcome the shortcomings of the Airbnb search form",
        "by interpreting the user's natural language requests and executing searches that match their intent",
        "using the additional context of the users descriptions from text and images."
    ),
    deps_type=AirbnbFilters,
    tools=[
        update_search_filters_tool,
        filter_listings_tool,
        smart_search_listings_tool,
    ],
)


@agent.instructions
def tool_usage_workflow(ctx: RunContext[AirbnbFilters]) -> str:
    """Tell the model when to search and how to show listings in chat."""
    return (
        "Tools (use these exact names):\n"
        "- `update_search_filters` — sync chat criteria into the search form\n"
        "- `search_airbnb` — structured filter search; opens structured listing results\n"
        "- `smart_search_listings` — semantic/vibe search; opens structured listing results\n\n"
        "Workflow:\n"
        "1. If the user mentions location, dates, budget, guests, amenities, or keywords, "
        "call `update_search_filters` first (only fields they mentioned). "
        "Put known Airbnb amenities (pool, gym, wifi, workspace, …) in `amenities`. "
        "Put anything else they want (balcony, patio, sauna, ocean view, …) in `keywords` — "
        "do not drop features just because they are not amenity filters.\n"
        "2. You need location, checkin, and nights before searching — ask if missing.\n"
        "3. When they want results (or confirm they want to search), call "
        "`search_airbnb` for normal filter searches, or `smart_search_listings` "
        "for vibe/style/semantic requests (and whenever the user attaches a "
        "reference image). Treat an attached image and their written description "
        "as complementary search context.\n"
        "4. After a search tool returns, reply with only a short 1–2 sentence summary. "
        "The UI displays the structured listings separately, so do not repeat them as "
        "markdown, links, or JSON.\n"
        "5. If nothing is found, tell the user and suggest adjusting criteria."
    )


@agent.instructions
def add_filters_to_context(ctx: RunContext[AirbnbFilters]) -> str:
    """Tell the model which search-form filters are already set."""
    values = ctx.deps.model_dump(exclude_none=True)
    if not values:
        return "The user has not set any search filters yet."
    lines = [f"- {key}: {value}" for key, value in values.items()]
    return "The user's current search filters are:\n" + "\n".join(lines)
