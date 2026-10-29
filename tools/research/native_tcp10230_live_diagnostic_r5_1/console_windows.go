//go:build windows

package main

import "syscall"

func init() {
	// Best-effort UTF-8 for Russian prompts on Windows console.
	kernel := syscall.NewLazyDLL("kernel32.dll")
	_, _, _ = kernel.NewProc("SetConsoleOutputCP").Call(65001)
	_, _, _ = kernel.NewProc("SetConsoleCP").Call(65001)
}
