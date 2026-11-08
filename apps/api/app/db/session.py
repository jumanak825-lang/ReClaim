"""Engine, sessions and the per-request / per-job transaction."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from ..core import config

_engine = None
_factory: sessionmaker[Session] | None = None
_current: ContextVar[Session | None] = ContextVar("db_session", default=None)


def engine():
    global _engine, _factory
    if _engine is None:
        _engine = create_engine(config.settings.database_url, pool_pre_ping=True, future=True)
        _factory = sessionmaker(bind=_engine, expire_on_commit=False, autoflush=True)
    return _engine


def reset_engine() -> None:
    """Drop the cached engine (tests switch DATABASE_URL)."""
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = _factory = None


def db() -> Session:
    """The session bound to the current request or worker job."""
    s = _current.get()
    if s is None:
        raise RuntimeError("No database session is active. Use transaction().")
    return s


@contextmanager
def transaction() -> Iterator[Session]:
    """One unit of work: commit on success, roll back on any exception."""
    engine()
    assert _factory is not None
    s = _factory()
    token = _current.set(s)
    try:
        yield s
        s.commit()
    except BaseException:
        s.rollback()
        raise
    finally:
        _current.reset(token)
        s.close()


async def get_db() -> AsyncIterator[Session]:
    """FastAPI dependency (use with scope="function": commit happens before the response is sent).

    Async on purpose: the session is bound in the request task's context, which FastAPI copies
    into the thread pool for sync endpoints and dependencies. A sync generator would bind it in
    a throwaway thread context that endpoints never see.
    """
    engine()
    assert _factory is not None
    s = _factory()
    token = _current.set(s)
    try:
        yield s
        await run_in_threadpool(s.commit)
    except BaseException:
        await run_in_threadpool(s.rollback)
        raise
    finally:
        try:
            _current.reset(token)
        except ValueError:  # exited in a different context; nothing to restore
            pass
        await run_in_threadpool(s.close)


def ping() -> bool:
    try:
        with engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
