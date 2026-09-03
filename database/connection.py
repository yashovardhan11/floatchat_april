import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, func, select, and_
from sqlalchemy.orm import Session

from config.settings import get_db_connection_string
from database.schema import Base, Measurement, Profile, SyncLog

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Central database access layer using SQLAlchemy 2.0 session patterns."""

    def __init__(self, config: dict) -> None:
        conn_str = get_db_connection_string(config)
        self.engine = create_engine(
            conn_str,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
        Base.metadata.create_all(self.engine)
        logger.info("DatabaseManager initialized, tables ensured")

    # ─── Insert operations ────────────────────────────────────────────────────

    def insert_profile(self, profile_data: dict) -> int:
        """Insert one profile; return existing id if duplicate float_id+cycle."""
        try:
            with Session(self.engine) as session:
                float_id = profile_data.get("float_id")
                cycle = profile_data.get("cycle_number")

                # Duplicate check
                existing = session.scalar(
                    select(Profile.id).where(
                        and_(
                            Profile.float_id == float_id,
                            Profile.cycle_number == cycle,
                        )
                    )
                )
                if existing is not None:
                    logger.debug(
                        "Profile already exists: float_id=%s cycle=%s → id=%s",
                        float_id,
                        cycle,
                        existing,
                    )
                    return existing

                profile = Profile(**profile_data)
                session.add(profile)
                session.commit()
                session.refresh(profile)
                logger.debug("Inserted profile id=%s", profile.id)
                return profile.id
        except Exception:
            logger.exception("Failed to insert profile float_id=%s", profile_data.get("float_id"))
            raise

    def insert_measurements(self, profile_id: int, measurements: list[dict]) -> int:
        """Bulk insert all measurements for a profile. Returns count inserted."""
        if not measurements:
            return 0
        try:
            with Session(self.engine) as session:
                objs = [
                    Measurement(profile_id=profile_id, **m) for m in measurements
                ]
                session.add_all(objs)
                session.commit()
                logger.debug(
                    "Inserted %d measurements for profile_id=%d",
                    len(objs),
                    profile_id,
                )
                return len(objs)
        except Exception:
            logger.exception(
                "Failed to insert measurements for profile_id=%d", profile_id
            )
            raise

    # ─── Query operations ─────────────────────────────────────────────────────

    def get_profiles(
        self,
        limit: int = 100,
        offset: int = 0,
        float_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        lat_min: float | None = None,
        lat_max: float | None = None,
        lon_min: float | None = None,
        lon_max: float | None = None,
    ) -> pd.DataFrame:
        """Return profiles matching provided filters as a DataFrame."""
        try:
            with Session(self.engine) as session:
                stmt = select(Profile)
                conditions = []
                if float_id:
                    conditions.append(Profile.float_id == float_id)
                if date_from:
                    conditions.append(Profile.measurement_date >= date_from)
                if date_to:
                    conditions.append(Profile.measurement_date <= date_to)
                if lat_min is not None:
                    conditions.append(Profile.latitude >= lat_min)
                if lat_max is not None:
                    conditions.append(Profile.latitude <= lat_max)
                if lon_min is not None:
                    conditions.append(Profile.longitude >= lon_min)
                if lon_max is not None:
                    conditions.append(Profile.longitude <= lon_max)
                if conditions:
                    stmt = stmt.where(and_(*conditions))
                stmt = stmt.order_by(Profile.measurement_date.desc()).offset(offset).limit(limit)
                rows = session.scalars(stmt).all()
                return self._profiles_to_df(rows)
        except Exception:
            logger.exception("Failed to get_profiles")
            return pd.DataFrame()

    def get_profiles_by_ids(self, profile_ids: list[int]) -> pd.DataFrame:
        """Get specific profiles by id list."""
        if not profile_ids:
            return pd.DataFrame()
        try:
            with Session(self.engine) as session:
                stmt = select(Profile).where(Profile.id.in_(profile_ids))
                rows = session.scalars(stmt).all()
                return self._profiles_to_df(rows)
        except Exception:
            logger.exception("Failed to get_profiles_by_ids")
            return pd.DataFrame()

    def get_measurements_by_profile(self, profile_id: int) -> pd.DataFrame:
        """Return all measurements for one profile."""
        try:
            with Session(self.engine) as session:
                stmt = (
                    select(Measurement)
                    .where(Measurement.profile_id == profile_id)
                    .order_by(Measurement.depth)
                )
                rows = session.scalars(stmt).all()
                return self._measurements_to_df(rows)
        except Exception:
            logger.exception(
                "Failed to get_measurements_by_profile profile_id=%d", profile_id
            )
            return pd.DataFrame()

    def get_profile_count(self) -> int:
        try:
            with Session(self.engine) as session:
                return session.scalar(select(func.count(Profile.id))) or 0
        except Exception:
            logger.exception("Failed to get_profile_count")
            return 0

    def get_float_count(self) -> int:
        try:
            with Session(self.engine) as session:
                return (
                    session.scalar(
                        select(func.count(func.distinct(Profile.float_id)))
                    )
                    or 0
                )
        except Exception:
            logger.exception("Failed to get_float_count")
            return 0

    def get_latest_sync_date(self) -> datetime | None:
        try:
            with Session(self.engine) as session:
                return session.scalar(
                    select(func.max(SyncLog.sync_date)).where(
                        SyncLog.status == "success"
                    )
                )
        except Exception:
            logger.exception("Failed to get_latest_sync_date")
            return None

    def get_date_range(self) -> tuple[datetime | None, datetime | None]:
        try:
            with Session(self.engine) as session:
                min_date = session.scalar(select(func.min(Profile.measurement_date)))
                max_date = session.scalar(select(func.max(Profile.measurement_date)))
                return min_date, max_date
        except Exception:
            logger.exception("Failed to get_date_range")
            return None, None

    def get_statistics(self) -> dict:
        """Return aggregate statistics across the entire dataset."""
        try:
            with Session(self.engine) as session:
                total_profiles = session.scalar(select(func.count(Profile.id))) or 0
                total_floats = (
                    session.scalar(
                        select(func.count(func.distinct(Profile.float_id)))
                    )
                    or 0
                )
                total_measurements = (
                    session.scalar(select(func.count(Measurement.id))) or 0
                )
                min_date = session.scalar(select(func.min(Profile.measurement_date)))
                max_date = session.scalar(select(func.max(Profile.measurement_date)))

                param_ranges = {}
                for col_name in (
                    "temperature",
                    "salinity",
                    "pressure",
                    "depth",
                    "oxygen",
                    "nitrate",
                    "ph",
                    "chlorophyll",
                ):
                    col = getattr(Measurement, col_name)
                    mn = session.scalar(select(func.min(col)))
                    mx = session.scalar(select(func.max(col)))
                    if mn is not None and mx is not None:
                        param_ranges[col_name] = {"min": mn, "max": mx}

                return {
                    "total_profiles": total_profiles,
                    "total_floats": total_floats,
                    "total_measurements": total_measurements,
                    "date_range": (min_date, max_date),
                    "param_ranges": param_ranges,
                }
        except Exception:
            logger.exception("Failed to get_statistics")
            return {
                "total_profiles": 0,
                "total_floats": 0,
                "total_measurements": 0,
                "date_range": (None, None),
                "param_ranges": {},
            }

    def profile_exists(self, float_id: str, cycle_number: int) -> bool:
        try:
            with Session(self.engine) as session:
                result = session.scalar(
                    select(Profile.id).where(
                        and_(
                            Profile.float_id == float_id,
                            Profile.cycle_number == cycle_number,
                        )
                    )
                )
                return result is not None
        except Exception:
            logger.exception(
                "Failed to check profile_exists float_id=%s cycle=%s",
                float_id,
                cycle_number,
            )
            return False

    # ─── Sync log ─────────────────────────────────────────────────────────────

    def log_sync(
        self,
        sync_type: str,
        files_downloaded: int,
        profiles_ingested: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        try:
            with Session(self.engine) as session:
                log_entry = SyncLog(
                    sync_date=datetime.utcnow(),
                    sync_type=sync_type,
                    files_downloaded=files_downloaded,
                    profiles_ingested=profiles_ingested,
                    status=status,
                    error_message=error_message,
                )
                session.add(log_entry)
                session.commit()
                logger.info(
                    "Sync logged: type=%s status=%s profiles=%d",
                    sync_type,
                    status,
                    profiles_ingested,
                )
        except Exception:
            logger.exception("Failed to log_sync")

    def get_sync_history(self, limit: int = 10) -> pd.DataFrame:
        try:
            with Session(self.engine) as session:
                stmt = (
                    select(SyncLog)
                    .order_by(SyncLog.sync_date.desc())
                    .limit(limit)
                )
                rows = session.scalars(stmt).all()
                if not rows:
                    return pd.DataFrame()
                return pd.DataFrame(
                    [
                        {
                            "id": r.id,
                            "sync_date": r.sync_date,
                            "sync_type": r.sync_type,
                            "files_downloaded": r.files_downloaded,
                            "profiles_ingested": r.profiles_ingested,
                            "status": r.status,
                            "error_message": r.error_message,
                        }
                        for r in rows
                    ]
                )
        except Exception:
            logger.exception("Failed to get_sync_history")
            return pd.DataFrame()

    def is_date_synced(self, date) -> bool:
        """Check if data for a specific date was already ingested successfully."""
        try:
            with Session(self.engine) as session:
                date_str = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)
                result = session.scalar(
                    select(SyncLog.id).where(
                        and_(
                            func.date(SyncLog.sync_date) == date_str,
                            SyncLog.status == "success",
                            SyncLog.profiles_ingested > 0,
                        )
                    )
                )
                return result is not None
        except Exception:
            logger.exception("Failed to is_date_synced for date=%s", date)
            return False

    # ─── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _profiles_to_df(rows) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(
            [
                {
                    "id": r.id,
                    "float_id": r.float_id,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "measurement_date": r.measurement_date,
                    "cycle_number": r.cycle_number,
                    "data_mode": r.data_mode,
                    "quality_flag": r.quality_flag,
                    "summary_text": r.summary_text,
                    "source_file": r.source_file,
                    "sync_date": r.sync_date,
                }
                for r in rows
            ]
        )

    @staticmethod
    def _measurements_to_df(rows) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(
            [
                {
                    "id": r.id,
                    "profile_id": r.profile_id,
                    "depth": r.depth,
                    "pressure": r.pressure,
                    "temperature": r.temperature,
                    "salinity": r.salinity,
                    "oxygen": r.oxygen,
                    "nitrate": r.nitrate,
                    "ph": r.ph,
                    "chlorophyll": r.chlorophyll,
                    "potential_temperature": r.potential_temperature,
                    "density": r.density,
                    "mixed_layer_depth": r.mixed_layer_depth,
                    "quality_flag": r.quality_flag,
                    "anomaly_flag": r.anomaly_flag,
                }
                for r in rows
            ]
        )
