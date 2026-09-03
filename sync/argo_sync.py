import ftplib
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from data_processing.data_transformer import DataTransformer
from data_processing.netcdf_processor import NetCDFProcessor

logger = logging.getLogger(__name__)

FTP_SERVER = "ftp.ifremer.fr"
INDIAN_OCEAN_PATH = "/ifremer/argo/geo/indian_ocean"
FILE_PATTERN = "{year}/{month:02d}/{date}_prof.nc"


class ArgoSyncEngine:
    """Downloads and ingests ARGO Indian Ocean data from Ifremer FTP."""

    def __init__(self, config: dict, db_manager, vector_store) -> None:
        self.config = config
        self.db = db_manager
        self.vs = vector_store
        self.download_path = Path(config["argo_download_path"])
        self.download_path.mkdir(parents=True, exist_ok=True)
        self.processor = NetCDFProcessor()
        self.transformer = DataTransformer()

    # ─── FTP connection ────────────────────────────────────────────────────────

    def connect(self) -> ftplib.FTP:
        """Connect to FTP server anonymously."""
        ftp = ftplib.FTP(timeout=30)
        ftp.connect(FTP_SERVER, 21)
        ftp.login()
        logger.info("Connected to FTP: %s", FTP_SERVER)
        return ftp

    def get_latest_available_date(self) -> date | None:
        """Scan FTP for the most recent date with a profile file."""
        try:
            ftp = self.connect()
            ftp.cwd(INDIAN_OCEAN_PATH)
            year = datetime.utcnow().year
            year_path = f"{INDIAN_OCEAN_PATH}/{year}"
            try:
                ftp.cwd(year_path)
            except ftplib.error_perm:
                year -= 1
                ftp.cwd(f"{INDIAN_OCEAN_PATH}/{year}")

            # List month directories
            months = []
            ftp.retrlines("LIST", lambda line: months.append(line.split()[-1]))
            months = sorted([m for m in months if m.isdigit()], reverse=True)

            for month in months:
                try:
                    ftp.cwd(f"{INDIAN_OCEAN_PATH}/{year}/{month}")
                    files = []
                    ftp.retrlines("NLST", files.append)
                    nc_files = sorted(
                        [f for f in files if f.endswith("_prof.nc")], reverse=True
                    )
                    if nc_files:
                        date_str = nc_files[0].replace("_prof.nc", "")
                        if len(date_str) == 8:
                            return datetime.strptime(date_str, "%Y%m%d").date()
                except Exception:
                    continue
            ftp.quit()
        except Exception:
            logger.exception("Failed to get_latest_available_date from FTP")
        return None

    # ─── Download ─────────────────────────────────────────────────────────────

    def is_today_downloaded(self) -> bool:
        """Return True only if file exists on disk AND sync_log records success."""
        today = datetime.utcnow().date()
        date_str = today.strftime("%Y%m%d")
        local_file = self.download_path / f"{date_str}_prof.nc"
        file_exists = local_file.exists()
        db_synced = self.db.is_date_synced(today)
        return file_exists and db_synced

    def download_file(self, target_date: date, ftp: ftplib.FTP | None = None) -> str:
        """Download the ARGO Indian Ocean profile file for target_date."""
        date_str = target_date.strftime("%Y%m%d")
        local_path = self.download_path / f"{date_str}_prof.nc"

        if local_path.exists():
            logger.info("File already downloaded: %s", local_path)
            return str(local_path)

        remote_path = (
            f"{INDIAN_OCEAN_PATH}/{target_date.year}/"
            f"{target_date.month:02d}/{date_str}_prof.nc"
        )
        close_ftp = False
        if ftp is None:
            ftp = self.connect()
            close_ftp = True

        try:
            logger.info("Downloading %s → %s", remote_path, local_path)
            file_size = 0
            try:
                file_size = ftp.size(remote_path)
            except Exception:
                pass

            bytes_downloaded = [0]

            def write_chunk(chunk: bytes) -> None:
                local_path.open("ab").write(chunk)
                bytes_downloaded[0] += len(chunk)
                if file_size:
                    pct = bytes_downloaded[0] / file_size * 100
                    logger.debug("Download progress: %.1f%%", pct)

            # Use a single file handle
            with local_path.open("wb") as f:
                ftp.retrbinary(f"RETR {remote_path}", f.write)

            logger.info("Download complete: %s (%.1f MB)", local_path, local_path.stat().st_size / 1e6)
            return str(local_path)
        except ftplib.error_perm as e:
            logger.warning("FTP permission error for %s: %s", remote_path, e)
            if local_path.exists():
                local_path.unlink()
            raise
        except Exception:
            logger.exception("Failed to download %s", remote_path)
            if local_path.exists():
                local_path.unlink()
            raise
        finally:
            if close_ftp:
                try:
                    ftp.quit()
                except Exception:
                    pass

    # ─── Ingest ───────────────────────────────────────────────────────────────

    def ingest_file(self, filepath: str) -> dict:
        """Process a downloaded NetCDF file into PostgreSQL and ChromaDB."""
        result = {
            "files_processed": 1,
            "profiles_ingested": 0,
            "profiles_skipped": 0,
            "errors": [],
        }

        try:
            raw_profiles = self.processor.process_file(filepath)
            logger.info("Parsed %d profiles from %s", len(raw_profiles), filepath)
        except Exception as e:
            logger.exception("Failed to parse %s", filepath)
            result["errors"].append(str(e))
            return result

        for raw in raw_profiles:
            meta = raw.get("metadata", {})
            meas_list = raw.get("measurements", [])

            float_id = meta.get("float_id", "UNKNOWN")
            cycle = meta.get("cycle_number")

            try:
                if self.db.profile_exists(float_id, cycle):
                    result["profiles_skipped"] += 1
                    continue

                import pandas as pd

                meas_df = pd.DataFrame(meas_list)
                meas_df = self.transformer.interpolate_missing_depth(meas_df)
                meas_df = self.transformer.clean_measurements(meas_df)
                meas_df = self.transformer.calculate_derived_parameters(meas_df)

                if meas_df.empty:
                    result["profiles_skipped"] += 1
                    continue

                summary = self.transformer.create_profile_summary(meas_df, meta)
                meta["summary_text"] = summary["summary_text"]
                meta["sync_date"] = datetime.utcnow()

                profile_id = self.db.insert_profile(meta)
                self.db.insert_measurements(profile_id, meas_df.to_dict("records"))
                self.vs.add_profile(summary, profile_id)

                result["profiles_ingested"] += 1
            except Exception as e:
                logger.exception(
                    "Failed to ingest profile float_id=%s cycle=%s", float_id, cycle
                )
                result["errors"].append(f"{float_id}/{cycle}: {e}")

        logger.info(
            "Ingestion complete: %d ingested, %d skipped, %d errors",
            result["profiles_ingested"],
            result["profiles_skipped"],
            len(result["errors"]),
        )
        return result

    # ─── Sync operations ──────────────────────────────────────────────────────

    def sync_today(self) -> dict:
        """Download and ingest today's ARGO data if not already done."""
        today = datetime.utcnow().date()

        if self.is_today_downloaded():
            logger.info("Today's data already synced")
            return {"status": "already_synced", "already_synced": True, "profiles_ingested": 0}

        try:
            filepath = self.download_file(today)
        except ftplib.error_perm:
            msg = f"Today's file ({today}) not yet available on FTP server"
            logger.warning(msg)
            self.db.log_sync("auto", 0, 0, "failed", msg)
            return {"status": "not_available", "already_synced": False, "error": msg}
        except Exception as e:
            logger.exception("Failed to download today's file")
            self.db.log_sync("auto", 0, 0, "failed", str(e))
            return {"status": "failed", "already_synced": False, "error": str(e)}

        try:
            ingest_result = self.ingest_file(filepath)
            status = "success" if not ingest_result["errors"] else "partial"
            self.db.log_sync(
                "auto",
                1,
                ingest_result["profiles_ingested"],
                status,
                "; ".join(ingest_result["errors"]) if ingest_result["errors"] else None,
            )
            return {
                "status": status,
                "already_synced": False,
                "profiles_ingested": ingest_result["profiles_ingested"],
                "profiles_skipped": ingest_result["profiles_skipped"],
                "errors": ingest_result["errors"],
            }
        except Exception as e:
            logger.exception("Failed to ingest today's file")
            self.db.log_sync("auto", 1, 0, "failed", str(e))
            return {"status": "failed", "already_synced": False, "error": str(e)}

    def sync_date_range(
        self,
        start: date,
        end: date,
        progress_callback=None,
    ) -> dict:
        """Download and ingest all dates in [start, end]."""
        total = {"profiles_ingested": 0, "profiles_skipped": 0, "errors": [], "dates_processed": 0}
        current = start
        while current <= end:
            if progress_callback:
                progress_callback(current)
            if not self.db.is_date_synced(current):
                try:
                    filepath = self.download_file(current)
                    r = self.ingest_file(filepath)
                    total["profiles_ingested"] += r["profiles_ingested"]
                    total["profiles_skipped"] += r["profiles_skipped"]
                    total["errors"].extend(r["errors"])
                    status = "success" if not r["errors"] else "partial"
                    self.db.log_sync("manual", 1, r["profiles_ingested"], status)
                except Exception as e:
                    logger.exception("Failed to sync date %s", current)
                    total["errors"].append(f"{current}: {e}")
                    self.db.log_sync("manual", 0, 0, "failed", str(e))
            total["dates_processed"] += 1
            current += timedelta(days=1)
        return total

    def get_sync_status(self) -> dict:
        """Return current sync status summary."""
        today = datetime.utcnow().date()
        latest_available = None
        try:
            latest_available = self.get_latest_available_date()
        except Exception:
            pass

        return {
            "last_sync_date": self.db.get_latest_sync_date(),
            "total_profiles": self.db.get_profile_count(),
            "today_downloaded": self.is_today_downloaded(),
            "today_date": today,
            "latest_available_date": latest_available,
            "sync_history": self.db.get_sync_history(limit=5),
        }

    def run_auto_sync(self) -> dict:
        """Called on app startup; sync today silently if not already done."""
        if self.is_today_downloaded():
            logger.info("Auto-sync: today's data already present, skipping")
            return {"status": "already_synced", "profiles_ingested": 0}

        logger.info("Auto-sync: starting today's sync")
        result = self.sync_today()
        logger.info("Auto-sync complete: %s", result)
        return result
