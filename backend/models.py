from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    Integer, String, Text, Boolean, DateTime, Date, ForeignKey,
    UniqueConstraint, Index, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
import enum

class RoleEnum(str, enum.Enum):
    provider = "provider"
    admin = "admin"

class StatusEnum(str, enum.Enum):
    draft = "draft"
    saved = "saved"

class Provider(Base):
    __tablename__ = "providers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[RoleEnum] = mapped_column(SAEnum(RoleEnum), default=RoleEnum.provider)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    encounters: Mapped[list["Encounter"]] = relationship(back_populates="provider")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="actor")
    drafts: Mapped[list["Draft"]] = relationship(back_populates="provider")

class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (UniqueConstraint("first_name", "last_name", "dob"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    dob: Mapped[date] = mapped_column(Date)
    encounters: Mapped[list["Encounter"]] = relationship(back_populates="patient")

class Template(Base):
    __tablename__ = "templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    system_prompt: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    encounters: Mapped[list["Encounter"]] = relationship(back_populates="template")

class Encounter(Base):
    __tablename__ = "encounters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id"))
    provider_id: Mapped[int] = mapped_column(Integer, ForeignKey("providers.id"))
    template_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("templates.id"), nullable=True)
    status: Mapped[StatusEnum] = mapped_column(SAEnum(StatusEnum), default=StatusEnum.draft)
    raw_input: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    patient: Mapped["Patient"] = relationship(back_populates="encounters")
    provider: Mapped["Provider"] = relationship(back_populates="encounters")
    template: Mapped[Optional["Template"]] = relationship(back_populates="encounters")
    note: Mapped[Optional["Note"]] = relationship(back_populates="encounter", uselist=False)
    draft: Mapped[Optional["Draft"]] = relationship(back_populates="encounter", uselist=False)

class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    encounter_id: Mapped[int] = mapped_column(Integer, ForeignKey("encounters.id"), unique=True)
    encounter: Mapped["Encounter"] = relationship(back_populates="note")
    versions: Mapped[list["NoteVersion"]] = relationship(back_populates="note", order_by="NoteVersion.version_no")

class NoteVersion(Base):
    __tablename__ = "note_versions"
    __table_args__ = (Index("ix_note_versions_note_version", "note_id", "version_no"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    note_id: Mapped[int] = mapped_column(Integer, ForeignKey("notes.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict] = mapped_column(JSONB)
    saved_by: Mapped[int] = mapped_column(Integer, ForeignKey("providers.id"))
    saved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    note: Mapped["Note"] = relationship(back_populates="versions")
    saver: Mapped["Provider"] = relationship(foreign_keys=[saved_by])

class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    encounter_id: Mapped[int] = mapped_column(Integer, ForeignKey("encounters.id"), unique=True)
    provider_id: Mapped[int] = mapped_column(Integer, ForeignKey("providers.id"))
    content: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    encounter: Mapped["Encounter"] = relationship(back_populates="draft")
    provider: Mapped["Provider"] = relationship(back_populates="drafts")

class ICD10Code(Base):
    __tablename__ = "icd10_codes"
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    description: Mapped[str] = mapped_column(String(500))
    embedding: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("providers.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extra: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    actor: Mapped[Optional["Provider"]] = relationship(back_populates="audit_logs")
