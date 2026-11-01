from apolo.services.server import ApoloServer, ApoloTaskManager, TaskInfo
from apolo.services.watcher import InboxWatcher

FolderWatcher = InboxWatcher

__all__ = [
    "ApoloServer",
    "ApoloTaskManager",
    "TaskInfo",
    "InboxWatcher",
    "FolderWatcher",
]
