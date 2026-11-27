"""R5 creation, reply test selection and guarded destructive actions."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base, utcnow
from app.db.models import Admin, Test, User
from app.services import test_manage_service as manage
from tests.helpers import MemoryState, bot, message


async def test_pdf_deletion_is_committed_and_rollback_safe(tmp_path, monkeypatch):
    """Filesystem cleanup follows commit and is cancelled by rollback."""

    monkeypatch.chdir(tmp_path)
    root = tmp_path / "storage/pdf"
    root.mkdir(parents=True)
    path = root / "draft.pdf"
    path.write_bytes(b"pdf")
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'delete.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory.begin() as session:
        user = User(tg_id=1, full_name="Owner")
        test = Test(
            code="5830",
            title="Draft",
            pdf_file_id="p",
            pdf_path=str(path),
            questions_count=1,
            answer_key={"1": "a"},
            status="draft",
            start_at=utcnow() + timedelta(days=1),
            scheduled_at=utcnow() + timedelta(days=1),
            created_by=1,
        )
        session.add_all([user, test, Admin(tg_id=1, role="owner")])
    user_id, test_id = user.id, test.id
    state, msg, api = MemoryState(), message(), bot()
    for rollback in (True, False):
        async with factory() as session:
            user = await session.get(type(user), user_id)
            await manage.card(msg, state, session, user, test_id)
            await manage.action(msg, state, session, api, user, "delete")
            assert path.exists()
            await manage.confirm(msg, state, session, api, user)
            assert path.exists()
            if rollback:
                await session.rollback()
                assert path.exists()
            else:
                await session.commit()
                assert not path.exists()
    await engine.dispose()
