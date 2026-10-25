"""Controlled read-only polling scheduler, with bounded retries after failures.

No interval is chosen by the software. Only explicitly configured intervals
schedule reads. No direct device queries are performed by browser API routes.
"""
from __future__ import annotations
import threading
import time
from typing import Callable

class PollScheduler:
    def __init__(self, collector, clock:Callable[[],float]=time.monotonic):
        self.collector=collector
        self.clock=clock
        self.due={}
        self.failures={}
        self.metrics={}
        self.lock=threading.RLock()

    def step(self):
        """Perform at most one polling operation per due device; intended for a background thread."""
        with self.collector.lock:
            devices=[dict(d) for d in self.collector.devices.values()]
        now=self.clock()
        active={d['id'] for d in devices if d.get('enabled') and d.get('interval_seconds') is not None}
        with self.lock:
            for key in list(self.due):
                if key not in active:
                    self.due.pop(key,None)
                    self.failures.pop(key,None)
        for device in devices:
            device_id=device['id']
            interval=device.get('interval_seconds')
            if device_id not in active:
                continue
            with self.lock:
                if now < self.due.get(device_id,now):
                    continue
                # Reserve a slot before I/O so the same device is never double-polled.
                self.due[device_id]=now+interval
            started=self.clock()
            try:
                self.collector.poll_once(device_id)
            except Exception as exc:
                with self.lock:
                    failures=self.failures.get(device_id,0)+1
                    self.failures[device_id]=failures
                    # Backoff cannot be faster than the configured interval.
                    delay=min(interval*(2**min(failures,6)),max(interval,300))
                    self.due[device_id]=self.clock()+delay
                    self.metrics[device_id]={
                        'state':'error','consecutive_failures':failures,
                        'last_duration_seconds':round(self.clock()-started,4),
                        'next_attempt_not_before_monotonic':self.due[device_id],
                        'last_error_type':type(exc).__name__}
            else:
                with self.lock:
                    self.failures[device_id]=0
                    self.due[device_id]=self.clock()+interval
                    self.metrics[device_id]={
                        'state':'ok','consecutive_failures':0,
                        'last_duration_seconds':round(self.clock()-started,4),
                        'next_attempt_not_before_monotonic':self.due[device_id],
                        'last_error_type':None}

    def status(self):
        with self.lock:
            return {k:dict(v) for k,v in self.metrics.items()}
