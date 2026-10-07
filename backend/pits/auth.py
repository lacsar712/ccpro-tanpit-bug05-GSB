from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from ninja.security import HttpBearer

from pits.models import User


SESSION_EPOCH = 0


def bump_session_epoch() -> int:
    global SESSION_EPOCH
    SESSION_EPOCH += 1
    return SESSION_EPOCH


def make_token(username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=12)
    return jwt.encode(
        {"sub": username, "exp": exp, "epoch": SESSION_EPOCH},
        settings.JWT_SECRET,
        algorithm="HS256",
    )


class BearerAuth(HttpBearer):
    def authenticate(self, request, token: str):
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        except jwt.PyJWTError:
            return None
        if payload.get("epoch", 0) != SESSION_EPOCH:
            return None
        username = payload.get("sub")
        if not username:
            return None
        return User.objects.filter(username=username).first()
