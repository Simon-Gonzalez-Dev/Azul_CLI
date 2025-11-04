"""File monitoring with watchdog."""

import threading
from pathlib import Path
from typing import Optional, Callable
from queue import Queue

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

from azul.config.manager import get_config_manager


class FileChangeHandler(FileSystemEventHandler):
    """Handles file system events."""
    
    def __init__(self, callback: Callable[[str], None]):
        """Initialize handler with callback."""
        self.callback = callback
        self.modified_files = set()
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory and isinstance(event, FileModifiedEvent):
            file_path = Path(event.src_path)
            # Avoid duplicate notifications
            if file_path not in self.modified_files:
                self.modified_files.add(file_path)
                self.callback(str(file_path))
                # Clear after a delay to allow re-notification
                threading.Timer(2.0, lambda: self.modified_files.discard(file_path)).start()


class FileMonitor:
    """Monitors file changes in the project directory."""
    
    def __init__(self, project_root: Optional[Path] = None):
        """Initialize file monitor."""
        self.config = get_config_manager()
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.enabled = self.config.get("enable_file_monitoring", True) and WATCHDOG_AVAILABLE
        self.observer: Optional[Observer] = None
        self.notification_queue: Queue = Queue()
        self.callback: Optional[Callable[[str], None]] = None
    
    def start(self, callback: Optional[Callable[[str], None]] = None) -> None:
        """Start monitoring file changes."""
        if not self.enabled:
            return
        
        self.callback = callback
        
        if self.observer is None:
            self.observer = Observer()
            event_handler = FileChangeHandler(self._on_file_change)
            self.observer.schedule(event_handler, str(self.project_root), recursive=True)
            self.observer.start()
    
    def stop(self) -> None:
        """Stop monitoring file changes."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
    
    def _on_file_change(self, file_path: str) -> None:
        """Handle file change notification."""
        if self.callback:
            self.callback(file_path)
        else:
            self.notification_queue.put(file_path)
    
    def get_notifications(self) -> list:
        """Get pending file change notifications."""
        notifications = []
        while not self.notification_queue.empty():
            notifications.append(self.notification_queue.get())
        return notifications


# Global file monitor instance
_file_monitor: Optional[FileMonitor] = None


def get_file_monitor(project_root: Optional[Path] = None) -> FileMonitor:
    """Get the global file monitor instance."""
    global _file_monitor
    if _file_monitor is None:
        _file_monitor = FileMonitor(project_root)
    return _file_monitor

