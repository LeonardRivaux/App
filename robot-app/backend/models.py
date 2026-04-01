from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class MissionDB(Base):
    __tablename__ = "missions"

    id = Column(Integer, primary_key=True, index=True)
    start = Column(String, nullable=False)
    end = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")