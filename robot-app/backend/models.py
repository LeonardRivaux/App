from sqlalchemy import Column, Integer, String, ForeignKey
from database import Base


class RobotDB(Base):
    __tablename__ = "robots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="available")
    ip_address = Column(String, nullable=True)


class MissionDB(Base):
    __tablename__ = "missions"

    id = Column(Integer, primary_key=True, index=True)
    start = Column(String, nullable=False)
    end = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    robot_id = Column(Integer, ForeignKey("robots.id"), nullable=True)