from fastapi import APIRouter

from app.modules.astrology.routes import router as astrology
from app.modules.auth.routes import router as auth
from app.modules.cards.routes import router as cards
from app.modules.conversations.routes import router as conversations
from app.modules.health.routes import router as health
from app.modules.journal.routes import router as journal
from app.modules.readings.routes import router as readings
from app.modules.spreads.routes import router as spreads
from app.modules.users.routes import router as users

router = APIRouter()
for child, prefix, tag in [
    (health, "", "health"),
    (spreads, "/spreads", "spreads"),
    (cards, "/cards", "cards"),
    (auth, "/auth", "auth"),
    (users, "/me", "users"),
    (astrology, "/astrology", "astrology"),
    (readings, "/readings", "readings"),
    (conversations, "/readings", "conversations"),
    (journal, "/journal", "journal"),
]:
    router.include_router(child, prefix=prefix, tags=[tag])
