from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import os

# Get database URL directly from environment to avoid circular imports
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///llama_chat.db')

# Convert sync URL to async URL if needed
if DATABASE_URL.startswith('sqlite:///'):
    async_db_url = DATABASE_URL.replace('sqlite:///', 'sqlite+aiosqlite:///')
else:
    async_db_url = DATABASE_URL

# Create async engine
async_engine = create_async_engine(
    async_db_url,
    echo=False,
    future=True
)

# Create async session factory
async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

async def get_db():
    """Dependency to get async database session"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Initialize database tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)