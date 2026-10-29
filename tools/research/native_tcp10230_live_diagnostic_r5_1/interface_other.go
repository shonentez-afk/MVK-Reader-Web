//go:build !windows

package main

import "syscall"

// Non-Windows builds are used ONLY for offline/local QA. A selected local
// source IPv4 is still bound, while Windows uses IP_UNICAST_IF additionally.
func ipv4InterfaceControl(index int) func(string, string, syscall.RawConn) error {
	return nil
}
