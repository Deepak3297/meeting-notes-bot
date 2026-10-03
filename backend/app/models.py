from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .db import Base


class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)        # list + report header
    meeting_url = Column(String(500))                   # sent to Recall; shown on report
    bot_id = Column(String(100), index=True)            # webhook -> meeting lookup
    status = Column(String(20), default="joining")      # badge + polling stop condition
    summary = Column(Text)                              # summary card
    created_at = Column(DateTime, default=datetime.utcnow)  # list ordering
    segments = relationship("Segment", cascade="all, delete-orphan", order_by="Segment.id")
    decisions = relationship("Decision", cascade="all, delete-orphan")
    action_items = relationship("ActionItem", cascade="all, delete-orphan")


class Segment(Base):
    __tablename__ = "transcript_segments"
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    speaker = Column(String(100))                       # transcript tab + summarizer input
    text = Column(Text)
    timestamp = Column(Integer, default=0)              # seconds from start, shown as mm:ss


class Decision(Base):
    __tablename__ = "decisions"
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    text = Column(Text)


class ActionItem(Base):
    __tablename__ = "action_items"
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    task = Column(Text)
    owner = Column(String(100))
