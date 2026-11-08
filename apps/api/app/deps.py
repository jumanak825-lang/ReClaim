from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from .core import config
from .core.errors import ApiError
from .db.models import User
from .db.session import get_db
from .services import svc

# One session per request; committed before the response is sent (scope="function").
DB = Depends(get_db, scope="function")
DbSession = Annotated[Session, DB]


def current_user(request: Request, _db: DbSession) -> User:
    user = svc.session_user(request.cookies.get(config.settings.session_cookie_name))
    if not user:
        raise ApiError(401, "UNAUTHENTICATED", "Sign in to continue.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


class PageParams:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        cursor: Annotated[str | None, Query(description="Opaque value from meta.next_cursor.")] = None,
    ):
        self.limit = limit
        try:
            self.offset = max(0, int(cursor)) if cursor else 0
        except ValueError:
            raise ApiError(400, "INVALID_CURSOR", "The cursor is invalid.")

    def apply(self, items: list) -> tuple[list, str | None]:
        page = items[self.offset : self.offset + self.limit]
        nxt = self.offset + self.limit
        return page, (str(nxt) if nxt < len(items) else None)


Page = Annotated[PageParams, Depends()]
