import logging
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class Profile(Base):
    """One row per ARGO float dive (measurement session)."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    float_id: Mapped[str] = mapped_column(String(50), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    measurement_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cycle_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_mode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quality_flag: Mapped[int] = mapped_column(Integer, default=1)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sync_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    measurements: Mapped[list["Measurement"]] = relationship(
        "Measurement", back_populates="profile", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_profiles_float_id", "float_id"),
        Index("ix_profiles_measurement_date", "measurement_date"),
        Index("ix_profiles_float_cycle", "float_id", "cycle_number", unique=True),
    )

    def __repr__(self) -> str:
        return (
            f"<Profile id={self.id} float_id={self.float_id} "
            f"cycle={self.cycle_number} date={self.measurement_date}>"
        )


class Measurement(Base):
    """One row per depth level per profile."""

    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False
    )
    depth: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    salinity: Mapped[float | None] = mapped_column(Float, nullable=True)
    oxygen: Mapped[float | None] = mapped_column(Float, nullable=True)
    nitrate: Mapped[float | None] = mapped_column(Float, nullable=True)
    ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    chlorophyll: Mapped[float | None] = mapped_column(Float, nullable=True)
    potential_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    density: Mapped[float | None] = mapped_column(Float, nullable=True)
    mixed_layer_depth: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_flag: Mapped[int] = mapped_column(Integer, default=1)
    anomaly_flag: Mapped[bool] = mapped_column(Boolean, default=False)

    profile: Mapped["Profile"] = relationship("Profile", back_populates="measurements")

    __table_args__ = (Index("ix_measurements_profile_id", "profile_id"),)

    def __repr__(self) -> str:
        return (
            f"<Measurement id={self.id} profile_id={self.profile_id} "
            f"depth={self.depth} temp={self.temperature}>"
        )


class SyncLog(Base):
    """One row per sync operation (auto or manual)."""

    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sync_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sync_type: Mapped[str] = mapped_column(String(20), nullable=False)
    files_downloaded: Mapped[int] = mapped_column(Integer, default=0)
    profiles_ingested: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<SyncLog id={self.id} date={self.sync_date} "
            f"type={self.sync_type} status={self.status}>"
        )


# ─── Domain constants ─────────────────────────────────────────────────────────

QUALITY_FLAGS = {
    1: "Good data",
    2: "Probably good data",
    3: "Bad data potentially correctable",
    4: "Bad data",
    8: "Estimated value",
    9: "Missing value",
}

PARAMETER_RANGES = {
    "temperature": (-5, 50),
    "salinity": (0, 50),
    "pressure": (0, 10000),
    "depth": (0, 10000),
    "oxygen": (0, 500),
    "nitrate": (0, 100),
    "ph": (6, 9),
    "chlorophyll": (0, 100),
}


def validate_measurement_data(data: dict) -> bool:
    """Check all present measurement values are within PARAMETER_RANGES."""
    valid = True
    for param, (low, high) in PARAMETER_RANGES.items():
        value = data.get(param)
        if value is None:
            continue
        try:
            fval = float(value)
        except (TypeError, ValueError):
            logger.warning("Non-numeric value for %s: %s", param, value)
            valid = False
            continue
        if not (low <= fval <= high):
            logger.debug(
                "Out-of-range %s: %s (expected %s–%s)", param, fval, low, high
            )
            valid = False
    return valid
