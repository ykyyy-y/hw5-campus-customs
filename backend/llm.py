"""The one place a model is chosen for the Campus Customs team.

Every agent — Boss, Inventory, Accounting, Facilities, Customer Service — is built from
``build_model()``, so there is a single line in the project that names a model, and it
names **gpt-6-luna**. Nothing else is reachable.

Access goes through the Portkey gateway using ``PORTKEY_API_KEY`` from the repository
root ``.env``. The key is read into memory and never printed, logged, or written to the
audit trail.

The Responses API is used deliberately: function tools fail on Portkey's
chat/completions path for this model, and every agent here is tool-driven.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from portkey_ai import PORTKEY_GATEWAY_URL
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

# Where the key may live, nearest first. A grader who clones this repo on its own will put
# their .env in the project root; in the course repo it sits one level further up, shared
# across assignments. Both work without editing anything.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_CANDIDATES = (PROJECT_ROOT / ".env", PROJECT_ROOT.parent / ".env")
ENV_PATH = next((p for p in ENV_CANDIDATES if p.exists()), ENV_CANDIDATES[0])
load_dotenv(ENV_PATH)

#: The only model this assignment may use. Every agent is built from this constant.
MODEL_NAME = "gpt-6-luna"


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    """Return the shared gpt-6-luna model, reached through Portkey.

    Cached: the five agents share one client rather than opening five.
    """
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError(
            "PORTKEY_API_KEY is not set. Copy .env.example to .env in the project root "
            "and put your key in it. Looked in: "
            + ", ".join(str(p) for p in ENV_CANDIDATES)
        )
    provider = OpenAIProvider(api_key=api_key, base_url=PORTKEY_GATEWAY_URL)
    return OpenAIResponsesModel(MODEL_NAME, provider=provider)


# --------------------------------------------------------------------------- budgets
#
# Token control, enforced by the framework rather than asked for in a prompt.
#
# A specialist's healthy loop is: read the ticket, call one or two MCP tools, answer.
# A Boss turn is longer because it delegates and then acts. These ceilings sit above the
# normal path and below a runaway loop, so a mesh of five agents that starts talking to
# itself is stopped by the framework instead of by the bill.

#: Limits for a specialist agent answering one delegated question.
SPECIALIST_LIMITS = UsageLimits(request_limit=8, tool_calls_limit=10)

#: Limits for the Boss working one ticket, including its delegations.
BOSS_LIMITS = UsageLimits(request_limit=16, tool_calls_limit=24)
