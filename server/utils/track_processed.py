import json
from pathlib import Path
from datetime import datetime


class TrackProcessedCSVs:
    def __init__(self, csv_path):
        self.PROCESSED_FILE = Path("./data/processed_csvs.json")

        return


    def load_processed(self):
        """Return a Python set of processed CSV paths."""
        if not self.PROCESSED_FILE.exists():
            return set()

        try:
            with self.PROCESSED_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # ensure we return a set for easy membership tests
            return set(data)
        except json.JSONDecodeError:
            # file exists but is broken; start fresh
            return set()


    def save_processed(self, processed_set):
        """Save a set of processed CSV paths back to JSON."""
        data = sorted(processed_set)  # sort for nicer file
        with self.PROCESSED_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)


    def mark_processed(self, csv_path):
        """Add a CSV path to the list of processed files."""
        processed = self.load_processed()
        processed.add(str(csv_path))
        self.save_processed(processed)


class TrackProcessedCSVswithTimestamps:
    def __init__(self, csv_path):
        self.PROCESSED_FILE = Path("./data/processed_files.json")
        self.processed = self.has_been_processed(csv_path)
        if not self.processed:
            print(f'{csv_path} processed at {self.mark_processed(csv_path)}')
        return

    def load_processed(self):
        """
        Load processed CSV info.

        Returns:
            dict: { "path/to/file.csv": "timestamp", ... }
        """
        if not self.PROCESSED_FILE.exists():
            return {}

        try:
            with self.PROCESSED_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            # File exists but is not valid JSON; start fresh
            return {}
        
        # Expected new format: list of {"path": ..., "processed_at": ...}
        processed_dict = {}
        if isinstance(data, list):
            for item in data:
                # Be defensive in case of weird contents
                if not isinstance(item, dict):
                    continue
                path = item.get("path")
                ts = item.get("processed_at")
                if path is not None:
                    processed_dict[path] = ts

        return processed_dict


    def save_processed(self, processed_dict):
        """
        Save processed info back to JSON.

        Args:
            processed_dict (dict): { "path/to/file.csv": "timestamp", ... }
        """
        # Sort by path for stable, nice-looking JSON
        items = [
            {"path": path, "processed_at": processed_at}
            for path, processed_at in sorted(processed_dict.items())
        ]

        with self.PROCESSED_FILE.open("w", encoding="utf-8") as f:
            json.dump(items, f, indent=4, ensure_ascii=False)

        return


    def mark_processed(self, csv_path, processed_at=None):
        """
        Mark a CSV as processed, with timestamp.

        Args:
            csv_path: Path or str of the CSV.
            processed_at (str, optional): ISO8601 timestamp. If None, use now().

        Returns:
            str: The timestamp used.
        """
        if processed_at is None:
            processed_at = datetime.now().isoformat()

        processed = self.load_processed()
        processed[str(csv_path)] = processed_at
        self.save_processed(processed)
        return processed_at


    def has_been_processed(self, csv_path):
        """
        Check if a CSV has already been processed.

        Returns:
            bool
        """
        processed = self.load_processed()
        return str(csv_path) in processed

