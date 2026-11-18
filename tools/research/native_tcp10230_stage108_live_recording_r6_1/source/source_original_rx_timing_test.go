package main

import (
    "testing"
    "time"
)

func TestOriginalTMVKThreadConnectionAndReadTimeoutsFromIDP(t *testing.T) {
    if sourceOriginalConnectTimeout!=1000*time.Millisecond ||
       sourceOriginalReadTimeout!=5000*time.Millisecond {
        t.Fatal("original TMVKThread 00807C24..00807C39 timeout mismatch")
    }
    at:=time.Unix(0,0)
    if sourceOriginalReadTimedOut(at,at) ||
       sourceOriginalReadTimedOut(at,at.Add(4999*time.Millisecond)) {
        t.Fatal("original 5000ms ReadTimeout fired too early")
    }
    if !sourceOriginalReadTimedOut(at,at.Add(5000*time.Millisecond)) ||
       !sourceOriginalReadTimedOut(at,at.Add(6000*time.Millisecond)) {
        t.Fatal("original 5000ms ReadTimeout missing for passive Task2")
    }
    if sourceOriginalReadTimedOut(at,at.Add(-time.Millisecond)) {
        t.Fatal("future last packet cannot signal timeout")
    }
}
