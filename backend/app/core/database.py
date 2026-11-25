import json
from typing import Generator
from sqlalchemy import create_engine, TypeDecorator, JSON, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.app.core.config import settings
from backend.app.core.logging import logger

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class VectorType(TypeDecorator):
    """
    Platform-independent vector type.
    Uses pgvector's Vector type when running on PostgreSQL,
    and JSON when running on SQLite.
    """
    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 384, **kwargs):
        super().__init__(**kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector
                return dialect.type_descriptor(Vector(self.dim))
            except ImportError:
                return dialect.type_descriptor(JSON())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            if dialect.name == "postgresql":
                return [float(x) for x in value]
            return [float(x) for x in value]
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return list(value)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables, pgvector extension, and verify column dimensions."""
    if settings.DATABASE_URL.startswith("postgresql"):
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()
                logger.info("pgvector extension verified/created on PostgreSQL.")

                # Check and safely migrate embedding column dimension if changed
                dimension_check_sql = text("""
                    SELECT atttypmod 
                    FROM pg_attribute 
                    WHERE attrelid = 'document_chunks'::regclass 
                      AND attname = 'embedding' 
                      AND attnum > 0 
                      AND NOT attisdropped;
                """)
                try:
                    res = conn.execute(dimension_check_sql).fetchone()
                    if res and res[0] is not None and res[0] != settings.EMBEDDING_DIMENSION:
                        logger.info(
                            f"Migrating document_chunks.embedding dimension from {res[0]} to {settings.EMBEDDING_DIMENSION}"
                        )
                        conn.execute(
                            text(f"ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector({settings.EMBEDDING_DIMENSION});")
                        )
                        conn.commit()
                except Exception as mig_err:
                    # Table may not exist yet, which is expected before create_all
                    pass
        except Exception as e:
            logger.warning(f"Could not initialize pgvector extension: {e}")

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created successfully.")

    # Schema migration checks for newly added columns on existing tables
    if settings.DATABASE_URL.startswith("sqlite"):
        try:
            with engine.connect() as conn:
                cursor_res = conn.execute(text("PRAGMA table_info(response_drafts);")).fetchall()
                if cursor_res:
                    existing_cols = {col[1] for col in cursor_res}
                    if "order_product_mismatch" not in existing_cols:
                        logger.info("Migrating SQLite schema: adding response_drafts.order_product_mismatch")
                        conn.execute(text("ALTER TABLE response_drafts ADD COLUMN order_product_mismatch BOOLEAN DEFAULT 0 NOT NULL;"))
                        conn.commit()
                    if "mismatch_details" not in existing_cols:
                        logger.info("Migrating SQLite schema: adding response_drafts.mismatch_details")
                        conn.execute(text("ALTER TABLE response_drafts ADD COLUMN mismatch_details JSON DEFAULT '{}';"))
                        conn.commit()
                    if "answerability_details" not in existing_cols:
                        logger.info("Migrating SQLite schema: adding response_drafts.answerability_details")
                        conn.execute(text("ALTER TABLE response_drafts ADD COLUMN answerability_details JSON DEFAULT '{}';"))
                        conn.commit()

                # Migration check for documents table
                doc_res = conn.execute(text("PRAGMA table_info(documents);")).fetchall()
                if doc_res:
                    doc_cols = {col[1] for col in doc_res}
                    if "embedding_provider" not in doc_cols:
                        conn.execute(text("ALTER TABLE documents ADD COLUMN embedding_provider VARCHAR(50);"))
                    if "embedding_model" not in doc_cols:
                        conn.execute(text("ALTER TABLE documents ADD COLUMN embedding_model VARCHAR(100);"))
                    if "embedding_dimension" not in doc_cols:
                        conn.execute(text("ALTER TABLE documents ADD COLUMN embedding_dimension INTEGER;"))
                    conn.commit()

                # Migration check for document_chunks table
                chunk_res = conn.execute(text("PRAGMA table_info(document_chunks);")).fetchall()
                if chunk_res:
                    chunk_cols = {col[1] for col in chunk_res}
                    if "embedding_provider" not in chunk_cols:
                        conn.execute(text("ALTER TABLE document_chunks ADD COLUMN embedding_provider VARCHAR(50);"))
                    if "embedding_model" not in chunk_cols:
                        conn.execute(text("ALTER TABLE document_chunks ADD COLUMN embedding_model VARCHAR(100);"))
                    if "embedding_dimension" not in chunk_cols:
                        conn.execute(text("ALTER TABLE document_chunks ADD COLUMN embedding_dimension INTEGER;"))
                    conn.commit()
        except Exception as e:
            logger.warning(f"Error checking SQLite column migrations: {e}")
    elif settings.DATABASE_URL.startswith("postgresql"):
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE response_drafts ADD COLUMN IF NOT EXISTS order_product_mismatch BOOLEAN DEFAULT FALSE NOT NULL;"))
                conn.execute(text("ALTER TABLE response_drafts ADD COLUMN IF NOT EXISTS mismatch_details JSONB DEFAULT '{}'::jsonb;"))
                conn.execute(text("ALTER TABLE response_drafts ADD COLUMN IF NOT EXISTS answerability_details JSONB DEFAULT '{}'::jsonb;"))
                conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_provider VARCHAR(50);"))
                conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(100);"))
                conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_dimension INTEGER;"))
                conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_provider VARCHAR(50);"))
                conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(100);"))
                conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_dimension INTEGER;"))
                conn.commit()
        except Exception as e:
            logger.debug(f"Error checking PostgreSQL column migrations: {e}")
