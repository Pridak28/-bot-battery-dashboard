from __future__ import annotations
from typing import Callable
import schedule


class BotScheduler:
    def __init__(self):
        self.sched = schedule

    def daily(self, time_str: str, job: Callable):
        self.sched.every().day.at(time_str).do(job)

    def run_pending(self):
        self.sched.run_pending()
