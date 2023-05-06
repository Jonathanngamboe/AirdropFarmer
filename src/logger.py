import datetime
import os
from pathlib import Path
from datetime import timedelta
from config import settings
import logging
from logging.handlers import TimedRotatingFileHandler

class Logger:
    def __init__(self, user_id=None, log_dir='logs', app_log=False):
        self.user_id = user_id
        self.app_log = app_log
        if app_log:
            log_dir = Path(__file__).resolve().parent.parent / log_dir
        else:
            log_dir = Path(__file__).resolve().parent.parent / log_dir / str(
                self.user_id)  # Include user_id in the log_dir
        self.log_dir = Path(log_dir) if isinstance(log_dir, str) else log_dir
        self.log_filename = self.get_log_filename()
        self.ensure_log_file_exists()

        # Set up logging
        logger_name = "sys_log" if app_log else f"{self.user_id}_logger"
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)
        log_handler = TimedRotatingFileHandler(self.log_dir / self.log_filename, when="midnight", interval=1,
                                               backupCount=settings.LOG_MAX_AGE_DAYS)
        log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        log_handler.setFormatter(log_formatter)
        self.logger.addHandler(log_handler)

    def get_log_filename(self):
        today = datetime.datetime.now()
        if self.app_log:
            filename = f"app_{today.strftime('%Y-%m-%d')}.log"
        else:
            filename = f"user_{self.user_id}_{today.strftime('%Y-%m-%d')}.log"
        return filename

    def ensure_log_directory_exists(self):
        if not self.log_dir.exists():
            self.log_dir.mkdir(parents=True, exist_ok=True)

    def ensure_log_file_exists(self):
        log_path = self.log_dir / self.log_filename

        # Create the log directory if it does not exist
        if not self.log_dir.exists():
            os.makedirs(self.log_dir)

        # Create the log file if it does not exist
        if not log_path.exists():
            with open(log_path, 'w') as log_file:
                log_file.write(
                    f"--- Log file created on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n\n")

    def add_log(self, log_message, log_level=logging.INFO):
        if self.app_log:
            self.logger.log(log_level, log_message)
        else:
            log_path = self.log_dir / self.log_filename
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with log_path.open('a') as log_file:
                log_file.write(f"[{timestamp}] {log_message}\n")
            self.delete_old_logs()

    def get_logs(self, log_date=None):
        if log_date:
            log_filename = f"user_{self.user_id}_{log_date}.log"
        else:
            log_filename = self.log_filename

        log_path = self.log_dir / log_filename
        if log_path.exists():
            with open(log_path, 'r') as log_file:
                logs = log_file.read()
            return logs
        else:
            return None

    def get_log_file_path(self, date_str):
        log_filename = f"user_{self.user_id}_{date_str}.log"
        return self.log_dir / log_filename

    def get_log_dates(self):
        log_dates = []
        log_directory = Path(self.log_dir)
        if log_directory.exists():
            for log_file in log_directory.glob("*.log"):
                date_str = log_file.stem.split('_')[-1]
                log_dates.append(date_str)
        return log_dates

    def delete_old_logs(self, max_age_days=settings.LOG_MAX_AGE_DAYS):
        log_directory = Path(self.log_dir)
        if log_directory.exists():
            for log_file in log_directory.glob("*.log"):
                date_str = log_file.stem.split('_')[-1]
                log_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                if datetime.datetime.now() - log_date > timedelta(days=max_age_days):
                    os.remove(log_file)


