package main

import (
	"bufio"
	"encoding/binary"
	"errors"
	"fmt"
	"net"
	"sort"
	"strconv"
	"strings"
	"time"
)

// LocalNIC is an IPv4 address belonging to an UP, non-loopback interface.
// The operator must choose the wired Ethernet adapter: standard Go's
// net.Interface does not independently certify its physical media type.
type LocalNIC struct {
	Name   string
	Index  int
	IP     net.IP
	Prefix int
	MAC    string
}

func usableIPv4Interfaces() ([]LocalNIC, error) {
	ifaces, err := net.Interfaces()
	if err != nil {
		return nil, fmt.Errorf("enumerate network interfaces: %w", err)
	}
	out := make([]LocalNIC, 0)
	for _, iface := range ifaces {
		if iface.Flags&net.FlagUp == 0 || iface.Flags&net.FlagLoopback != 0 || iface.Index <= 0 {
			continue
		}
		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}
		for _, a := range addrs {
			n, ok := a.(*net.IPNet)
			if !ok || n.IP.To4() == nil {
				continue
			}
			ip := n.IP.To4()
			if !validIPv4(ip.String()) || ip.IsLoopback() || ip.IsLinkLocalUnicast() {
				continue
			}
			prefix, _ := n.Mask.Size()
			out = append(out, LocalNIC{Name: iface.Name, Index: iface.Index, IP: append(net.IP(nil), ip...), Prefix: prefix, MAC: iface.HardwareAddr.String()})
		}
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Index != out[j].Index {
			return out[i].Index < out[j].Index
		}
		return bytesLexLess(out[i].IP, out[j].IP)
	})
	return out, nil
}

func bytesLexLess(a, b net.IP) bool {
	for i := 0; i < 4; i++ {
		if a[i] != b[i] {
			return a[i] < b[i]
		}
	}
	return false
}

func printInterfaceChoices(items []LocalNIC) {
	fmt.Println("\nАктивные сетевые адаптеры с IPv4:")
	if len(items) == 0 {
		fmt.Println("  Нет подходящих адаптеров. Проверьте Ethernet и адрес IPv4.")
		return
	}
	for i, v := range items {
		fmt.Printf("  %d) %s | IPv4 %s/%d | индекс %d | MAC %s\n", i+1, v.Name, v.IP.String(), v.Prefix, v.Index, v.MAC)
	}
	fmt.Println("Выбирайте ПРАВИЛЬНУЮ проводную карту Ethernet из Windows.\nНе выбирайте Wi-Fi, VPN или виртуальный адаптер.")
}

func chooseNIC(reader *bufio.Reader, items []LocalNIC) (*LocalNIC, error) {
	printInterfaceChoices(items)
	if len(items) == 0 {
		return nil, errors.New("no active IPv4 interfaces")
	}
	answer := interactivePrompt(reader, "Номер проводного Ethernet-интерфейса (обязательно): ")
	idx, err := strconv.Atoi(answer)
	if err != nil || idx < 1 || idx > len(items) {
		return nil, errors.New("invalid Ethernet interface selection; no connection attempted")
	}
	nic := items[idx-1]
	fmt.Printf("Выбрано: %s, IPv4 %s, индекс %d\n", nic.Name, nic.IP, nic.Index)
	return &nic, nil
}

func findNICForLocalIPv4(ipText string, items []LocalNIC) (*LocalNIC, error) {
	ip := net.ParseIP(strings.TrimSpace(ipText)).To4()
	if ip == nil {
		return nil, fmt.Errorf("-local-ip must be a numeric IPv4 address")
	}
	for i := range items {
		if items[i].IP.Equal(ip) {
			nic := items[i]
			return &nic, nil
		}
	}
	return nil, fmt.Errorf("IPv4 %s not assigned to any UP, non-loopback interface; refusing automatic routing", ip)
}

// The Windows IPv4 IP_UNICAST_IF socket option expects an interface index in
// NETWORK byte order. This operation is pure, and independently unit tested.
func networkOrderIndex(index int) (int, error) {
	if index < 1 || index > 0xFFFFFF {
		return 0, fmt.Errorf("invalid IPv4 interface index %d", index)
	}
	var b [4]byte
	binary.BigEndian.PutUint32(b[:], uint32(index))
	return int(binary.LittleEndian.Uint32(b[:])), nil // Windows x64 is little endian.
}

func newInterfaceDialer(nic *LocalNIC) (*net.Dialer, error) {
	d := &net.Dialer{Timeout: 5 * time.Second, KeepAlive: -1}
	if nic == nil {
		return d, nil
	}
	if nic.Index < 1 || nic.IP.To4() == nil {
		return nil, errors.New("invalid chosen local interface")
	}
	if _, err := networkOrderIndex(nic.Index); err != nil {
		return nil, err
	}
	d.LocalAddr = &net.TCPAddr{IP: append(net.IP(nil), nic.IP.To4()...)}
	d.Control = ipv4InterfaceControl(nic.Index)
	return d, nil
}

func verifySelectedSource(c net.Conn, nic *LocalNIC) error {
	if nic == nil {
		return nil
	}
	a, ok := c.LocalAddr().(*net.TCPAddr)
	if !ok || !a.IP.Equal(nic.IP) {
		return fmt.Errorf("bound IPv4 mismatch: selected %s, socket reports %s", nic.IP, c.LocalAddr())
	}
	return nil
}
