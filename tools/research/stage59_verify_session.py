#!/usr/bin/env python3
"""Offline calendar-day guard: unsynchronized PCAP and VALUES must not be compared sample-by-sample."""
from pathlib import Path
import re,sys

def check(capture_date,values_name):
    hit=re.search(r"VALUES-(\\d{4}-\\d{2}-\\d{2})",values_name)
    if not hit: raise ValueError("filename needs VALUES-YYYY-MM-DD")
    return {"pcap_date":capture_date,"values_date":hit.group(1),"synchronized_date":capture_date==hit.group(1)}

if __name__=="__main__":
    assert not check("2026-10-26","VALUES-2026-10-27--11-18.csv")["synchronized_date"]
    assert not check("2026-10-26","VALUES-2026-10-28--10-11.csv")["synchronized_date"]
    print("PASS: Stage 59 rejects false date synchrony")
