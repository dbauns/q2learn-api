import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

print("DATABASE_URL =", repr(DATABASE_URL))

engine = create_engine(
    DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

from db_models import LearnerModel

print("Registered tables:", Base.metadata.tables.keys())

Base.metadata.create_all(bind=engine)