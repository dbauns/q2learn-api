from sqlalchemy import Column, DateTime, String
from datetime import datetime

from database import Base


class LearnerModel(Base):
    __tablename__ = "learners"

    id = Column(String, primary_key=True)
    email = Column(String)
    display_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)