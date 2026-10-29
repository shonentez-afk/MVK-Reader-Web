//go:build windows

package main

import (
	"syscall"
)

// Windows IP_UNICAST_IF (Winsock IPPROTO_IP option 31) fixes the outgoing
// physical/logical interface, instead of relying only on the routing table.
// The operator chooses the wired adapter; unknown media types are not guessed.
// This does NOT send any MVK protocol command or application data.
const winsockIPUnicastIF = 31

func ipv4InterfaceControl(index int) func(string, string, syscall.RawConn) error {
	return func(network, address string, raw syscall.RawConn) error {
		value, err := networkOrderIndex(index)
		if err != nil {
			return err
		}
		var socketErr error
		if err = raw.Control(func(fd uintptr) {
			socketErr = syscall.SetsockoptInt(syscall.Handle(fd), syscall.IPPROTO_IP, winsockIPUnicastIF, value)
		}); err != nil {
			return err
		}
		return socketErr // no silent fallback to Wi-Fi/VPN or system route
	}
}
