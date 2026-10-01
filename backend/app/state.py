import os, threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

executor=ThreadPoolExecutor(max_workers=max(1,int(os.getenv("WORKFLOW_WORKERS","1"))))
jobs: dict[str,dict[str,Any]]={}
jobs_lock=threading.Lock()
