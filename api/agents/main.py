import os
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from dotenv import load_dotenv

from api.tools.agent_search import smart_search_listings_tool
from api.tools.filter import AirbnbFilters, filter_listings_tool, update_search_filters_tool
from api.agents.vars import AIRBNB_AGENT_INSTRUCTIONS
from pydantic_ai.capabilities.hooks import Hooks
from pydantic_ai.models import ModelRequestContext

hooks = Hooks()

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
    instructions=AIRBNB_AGENT_INSTRUCTIONS,
    deps_type=AirbnbFilters,
    tools=[
        update_search_filters_tool,
        filter_listings_tool,
        smart_search_listings_tool,
    ],
    #capabilities=[hooks],
)


@agent.instructions
def summarize_search_criteria(ctx: RunContext[AirbnbFilters]) -> str:
    """Summarize the user's search criteria."""
    return """
    The injected AirbnbFilters values are already the user's active search
    criteria. Do not ask whether the user is ready when all required fields are
    present; use the appropriate search tool when the user submits or requests a
    search. Ask only for fields that are actually missing.
    """


@agent.instructions
def add_filters_to_context(ctx: RunContext[AirbnbFilters]) -> str:
    """Tell the model which search-form filters are already set."""
    values = ctx.deps.model_dump(exclude_none=True)
    if not values:
        return "The user has not set any search filters yet."
    lines = [f"- {key}: {value}" for key, value in values.items()]
    return "The user's current search filters are:\n" + "\n".join(lines)


@agent.instructions
def treat_form_state_as_authoritative(ctx: RunContext[AirbnbFilters]) -> str:
    """Prevent the agent from treating injected form state as conversation memory."""
    return """
    The AirbnbFilters dependency is authoritative application state supplied by
    the search form. It is not conversation memory and must not be described as
    unavailable. Never tell the user that you cannot remember or that they need
    to repeat filters that appear in the current search state.
    """


@agent.instructions
def route_visitor_policy_requests(ctx: RunContext[AirbnbFilters]) -> str:
    """Route visitor and house-rule preferences through semantic search."""
    return """
    Treat requests about visitors, guests who are not part of the booking, or
    house rules about additional people as natural-language search requests.
    This includes but is not limited to wording such as:
    - "allow visitors", "can I have friends over", or "friends can visit"
    - "overnight guests are allowed" or "my partner may stay over"
    - "no visitor restrictions" or "guests can come and go"
    - "exclude places that don't allow visitors"
    - "avoid listings with no guests/visitors", "no parties", or similar
      house-rule language
    Always use smart_search_listings for these requests and pass the user's
    wording unchanged in the query.
    For positive requests such as "and that allows visitors", a listing whose
    rules explicitly say visitors are not allowed is a contradictory result,
    not a match.
    Do not claim that visitor policies are unsupported, and do not redirect the
    user to an unrelated preference. Do not add visitor-policy text to the
    structured search filters.
    """


@hooks.on.before_model_request
async def debug_model_request(ctx, request_context: ModelRequestContext):
    print("\n===== OUTGOING LLM REQUEST =====", flush=True)
    for message in request_context.messages:
        print(message, flush=True)
    print("===== END REQUEST =====\n", flush=True)
    return request_context