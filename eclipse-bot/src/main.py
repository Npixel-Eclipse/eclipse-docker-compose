"""Eclipse Bot - Orchestration Platform Entrypoint."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.config import get_settings
from src.core import SlackIntegration, PerforceClient
from src.core.context import get_context
# Import Dispatcher
from src.core.dispatcher import handle_event_trigger
# Import API Router
from src.api.routes import router as api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    settings = get_settings()
    ctx = get_context()

    logger.info("Starting Eclipse Orchestration Platform...")

    # Initialize Singleton Clients
    ctx.slack = SlackIntegration(
        bot_token=settings.slack_bot_token,
        app_token=settings.slack_app_token,
    )
    ctx.p4 = PerforceClient()
    
    # Slack Event Registration
    @ctx.slack.on_mention
    async def handle_mention(event: dict, say):
        await handle_event_trigger(event, say, trigger_type="mention")

    @ctx.slack.on_message
    async def handle_any_message(event: dict, say):
        channel = event.get("channel", "")
        if channel.startswith("D"): # Handle DMs
            await handle_event_trigger(event, say, trigger_type="dm")

    await ctx.slack.start()
    yield
    await ctx.slack.stop()


app = FastAPI(lifespan=lifespan)
# Register API Routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "platform": "eclipse-orchestrator"}
