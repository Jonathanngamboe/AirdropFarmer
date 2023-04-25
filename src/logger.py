# logger.py

import datetime
from pathlib import Path

class Logger:
    def __init__(self, user_id, log_dir='logs'):
        log_dir = Path(__file__).resolve().parent.parent / 'logs' # Get the absolute path of the project root directory and append the logs directory
        self.log_dir = Path(log_dir) if isinstance(log_dir, str) else log_dir
        self.user_id = user_id
        self.log_filename = self.get_log_filename()
        self.ensure_log_file_exists()

    def get_log_filename(self):
        today = datetime.datetime.now()
        filename = f"user_{self.user_id}_{today.strftime('%Y-%m-%d')}.log"
        return filename

    def ensure_log_file_exists(self):
        log_dir = Path(self.log_dir)
        if not log_dir.exists():
            log_dir.mkdir(parents=True, exist_ok=True)

        log_path = log_dir / self.log_filename

        if not log_path.exists():
            with open(log_path, 'w') as log_file:
                log_file.write(
                    f"--- Log file created on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n\n")

    def add_log(self, log_message):
        log_path = self.log_dir / self.log_filename
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with log_path.open('a') as log_file:
            log_file.write(f"[{timestamp}] {log_message}\n")
