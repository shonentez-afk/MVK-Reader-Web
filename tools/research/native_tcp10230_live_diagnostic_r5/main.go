package main

import (
	"bufio"
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

func defaultOutput() string {
	home, e := os.UserHomeDir()
	if e == nil {
		documents := filepath.Join(home, "Documents")
		if st, e := os.Stat(documents); e == nil && st.IsDir() {
			return filepath.Join(documents, "MVK10230_Tests")
		}
		return filepath.Join(home, "MVK10230_Tests")
	}
	return "MVK10230_Tests"
}
func newRunDirectory(root string) (string, error) {
	if err := os.MkdirAll(root, 0700); err != nil {
		return "", err
	}
	for i := 0; i < 100; i++ {
		name := "TEST_" + time.Now().Format("2006-01-02_15-04-05.000")
		if i > 0 {
			name += fmt.Sprintf("_%d", i)
		}
		dir := filepath.Join(root, name)
		if _, err := os.Stat(dir); errors.Is(err, os.ErrNotExist) {
			return dir, nil
		}
		time.Sleep(time.Millisecond)
	}
	return "", errors.New("unable to allocate a unique test directory")
}
func interactivePrompt(reader *bufio.Reader, prompt string) string {
	fmt.Print(prompt)
	val, _ := reader.ReadString('\n')
	return strings.TrimSpace(val)
}
func validIPv4(ip string) bool {
	x := net.ParseIP(ip)
	if x == nil || x.To4() == nil {
		return false
	}
	v := x.To4()
	if v[0] == 0 || v[0] >= 224 || (v[0] == 255) {
		return false
	}
	return true
}

func liveCapture(ctx context.Context, m *Monitor, ip string, seconds int, maxBytes uint64) (string, error) {
	return liveCaptureAddress(ctx, m, net.JoinHostPort(ip, strconv.Itoa(instrumentPort)), seconds, maxBytes)
}

// The test-only indirection allows a local fake server on a random port.
// Production always invokes liveCapture with the fixed instrumentPort.
func liveCaptureAddress(ctx context.Context, m *Monitor, addr string, seconds int, maxBytes uint64) (string, error) {
	fmt.Printf("\nСоединение с %s (только чтение)...\n", addr)
	// Only Dial, SetReadDeadline and Read. No socket Write/Send calls anywhere.
	c, e := net.DialTimeout("tcp", addr, 5*time.Second)
	if e != nil {
		return "CONNECT_FAILED", fmt.Errorf("connect: %w", e)
	}
	defer c.Close()
	start := time.Now()
	deadline := start.Add(time.Duration(seconds) * time.Second)
	buf := make([]byte, 64*1024)
	lastPrinted := time.Time{}
	for {
		if ctx.Err() != nil {
			return "STOPPED_BY_USER", nil
		}
		if !time.Now().Before(deadline) {
			return "DURATION_REACHED", nil
		}
		if m.summary.RawBytes >= maxBytes {
			return "SIZE_LIMIT_REACHED", nil
		}
		timeout := time.Now().Add(time.Second)
		if timeout.After(deadline) {
			timeout = deadline
		}
		if e := c.SetReadDeadline(timeout); e != nil {
			return "READ_DEADLINE_FAILED", e
		}
		n, e := c.Read(buf)
		if n > 0 {
			remaining := maxBytes - m.summary.RawBytes
			limit := false
			if uint64(n) > remaining {
				n = int(remaining)
				limit = true
			}
			if err := m.ProcessChunk(buf[:n], time.Now()); err != nil {
				return "LOCAL_WRITE_FAILED", err
			}
			if time.Since(lastPrinted) >= 2*time.Second {
				fmt.Printf("Получено %.2f МБ | кадров %d | AUX4700 %d | ADC1 %d отсчётов\n",
					float64(m.summary.RawBytes)/1048576, m.summary.TotalFrames, m.summary.Aux4700, m.summary.Channels[0].Samples)
				lastPrinted = time.Now()
			}
			if limit {
				return "SIZE_LIMIT_REACHED", nil
			}
		}
		if e != nil {
			if errors.Is(e, io.EOF) {
				return "REMOTE_DISCONNECTED", nil
			}
			if ne, ok := e.(net.Error); ok && ne.Timeout() {
				continue
			}
			if ctx.Err() != nil {
				return "STOPPED_BY_USER", nil
			}
			return "SOCKET_READ_FAILED", e
		}
	}
}

func replayRaw(m *Monitor, path string, maxBytes uint64) (string, error) {
	f, e := os.Open(path)
	if e != nil {
		return "REPLAY_OPEN_FAILED", e
	}
	defer f.Close()
	buf := make([]byte, 64*1024)
	for {
		remaining := maxBytes - m.summary.RawBytes
		if remaining == 0 {
			return "SIZE_LIMIT_REACHED", nil
		}
		n, e := f.Read(buf)
		if n > 0 {
			if uint64(n) > remaining {
				n = int(remaining)
			}
			if err := m.ProcessChunk(buf[:n], time.Now()); err != nil {
				return "REPLAY_OUTPUT_WRITE_FAILED", err
			}
			if m.summary.RawBytes >= maxBytes {
				return "SIZE_LIMIT_REACHED", nil
			}
		}
		if e != nil {
			if errors.Is(e, io.EOF) {
				return "REPLAY_EOF", nil
			}
			return "REPLAY_READ_FAILED", e
		}
	}
}

func mainInner() int {
	ip := flag.String("ip", "", "IPv4 address of MVK instrument; always port 10230")
	seconds := flag.Int("seconds", 15, "live capture duration seconds (1..300)")
	out := flag.String("out", defaultOutput(), "root output folder")
	approve := flag.Bool("approve", false, "explicit approval to connect to industrial instrument")
	replay := flag.String("replay", "", "offline replay of captured incoming.raw (no network access)")
	limitMB := flag.Int("max-mb", 256, "maximum raw capture size in MiB (1..2048)")
	flag.Parse()
	interactive := len(os.Args) == 1
	input := bufio.NewReader(os.Stdin)
	if interactive {
		defer func() { _ = interactivePrompt(input, "\nНажмите ENTER для закрытия окна: ") }()
	}
	fmt.Println("==============================================================")
	fmt.Println("     MVK Reader Web - Native TCP/10230 LIVE Diagnostic R5")
	fmt.Println("     ПАССИВНЫЙ ПРИЕМ - НИКАКИХ КОМАНД ПРИБОРУ")
	fmt.Println("==============================================================")
	fmt.Println("Программа НЕ отправляет настройки, частоту или команду Flash.")
	fmt.Println("Сам факт TCP-подключения может влиять на прибор: нужен допуск.")
	if interactive {
		*ip = interactivePrompt(input, "IP-адрес МВК01 (например, 192.168.1.83): ")
		val := interactivePrompt(input, "Время записи, секунд [15]: ")
		if val != "" {
			n, e := strconv.Atoi(val)
			if e != nil {
				fmt.Println("Неверное число:", e)
				return 2
			}
			*seconds = n
		}
		fmt.Printf("Папка результатов: %s\n", *out)
		answer := interactivePrompt(input, "Подтверждаю разрешение на подключение. Введите YES: ")
		*approve = strings.EqualFold(answer, "YES")
	}
	if *limitMB < 1 || *limitMB > 2048 {
		fmt.Println("Неверный лимит MB (1..2048)")
		return 2
	}
	if *replay == "" {
		if !validIPv4(*ip) {
			fmt.Println("Необходимо указать действительный числовой IPv4 прибора")
			return 2
		}
		if *seconds < 1 || *seconds > 300 {
			fmt.Println("Время должно быть от 1 до 300 секунд")
			return 2
		}
		if !*approve {
			fmt.Println("Нет подтверждения разрешения на подключение; отменено без сетевых действий")
			return 2
		}
	}
	dir, e := newRunDirectory(*out)
	if e != nil {
		fmt.Println("Не могу создать папку:", e)
		return 2
	}
	mode := "LIVE_READ_ONLY"
	if *replay != "" {
		mode = "OFFLINE_REPLAY"
	}
	m, e := NewMonitor(dir, mode, *ip)
	if e != nil {
		fmt.Println("Ошибка создания файлов:", e)
		return 2
	}
	var reason string
	var runError error
	if *replay != "" {
		fmt.Printf("ОФЛАЙН: анализ файла %s (сеть не используется)\n", *replay)
		reason, runError = replayRaw(m, *replay, uint64(*limitMB)*1024*1024)
	} else {
		ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
		defer stop()
		reason, runError = liveCapture(ctx, m, *ip, *seconds, uint64(*limitMB)*1024*1024)
	}
	if runError != nil {
		fmt.Println("Ошибка:", runError)
		m.warn(runError.Error())
	}
	report, zipPath, finalErr := m.Finalize(reason)
	if finalErr != nil {
		fmt.Println("Ошибка завершения журнала:", finalErr)
		return 1
	}
	fmt.Println("\n=== РЕЗУЛЬТАТ ===")
	fmt.Printf("Получено байт: %d; кадров: %d; AUX4700: %d; снимков регистров: %d\n",
		report.RawBytes, report.TotalFrames, report.Aux4700, report.FullSnapshots)
	fmt.Printf("Причина завершения: %s; состояние: %s\n", report.EndReason, report.Result)
	if report.TailBytes > 0 {
		fmt.Printf("Незавершенный последний кадр: %d байт (помечен)\n", report.TailBytes)
	}
	fmt.Println("Архив для анализа:", zipPath)
	fmt.Println("Все файлы:", dir)
	if report.RawBytes == 0 {
		fmt.Println("Нет входящего потока. Возможно прибор ожидает команду; программа её НЕ отправляет.")
	}
	if report.CaptureOnly {
		fmt.Println("Найден неизвестный/ошибочный кадр. Все последующие байты сохранены в incoming.raw.")
	}
	if runError != nil {
		return 1
	}
	return 0
}
func main() { os.Exit(mainInner()) }
