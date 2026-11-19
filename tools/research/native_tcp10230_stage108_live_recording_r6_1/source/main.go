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

func liveCapture(ctx context.Context, m *Monitor, ip string, seconds int, maxBytes uint64, nic *LocalNIC) (string, error) {
	// Original Task2 retry is independent of hardware SetRate.
	// Passive reconnect requires its own explicit operator approval.
	if m.sourceTask2TX != nil || m.sourceAfterRAWReconnect {
		return sourceTask2CaptureInitialRetry(ctx,m,ip,seconds,maxBytes,nic)
	}
	return liveCaptureAddressOnNIC(ctx, m, net.JoinHostPort(ip, strconv.Itoa(instrumentPort)), seconds, maxBytes, nic)
}

// The test-only indirection allows a local fake server on a random port.
// Production always invokes liveCapture with the fixed instrumentPort.
func liveCaptureAddress(ctx context.Context, m *Monitor, addr string, seconds int, maxBytes uint64) (string, error) {
	// Test-only compatibility path; production always requires a selected NIC.
	return liveCaptureAddressOnNIC(ctx, m, addr, seconds, maxBytes, nil)
}

func liveCaptureAddressOnNIC(ctx context.Context, m *Monitor, addr string, seconds int, maxBytes uint64, nic *LocalNIC) (reason string, resultErr error) {
	fmt.Printf("\nСоединение с %s (только чтение)...\n", addr)
	if nic != nil {
		m.summary.SelectedInterface = nic.Name
		m.summary.SelectedInterfaceIndex = nic.Index
		m.summary.SelectedLocalIPv4 = nic.IP.String()
		m.note(fmt.Sprintf("Chosen interface %s (index %d), source IPv4 %s", nic.Name, nic.Index, nic.IP))
		fmt.Printf("Ethernet-интерфейс: %s | индекс %d | локальный IPv4 %s\n", nic.Name, nic.Index, nic.IP)
	}
	dialer, e := newInterfaceDialer(nic)
	if e==nil { dialer.Timeout=sourceOriginalConnectTimeout }
    // Original _Unit125:00807C24..00807C39 sets 1000ms/5000ms
    // for TMVKThread regardless of whether outbound SetRate is approved.
	if e != nil {
		return "LOCAL_INTERFACE_INVALID", e
	}
	// TCP Connect starts streaming even WITHOUT an application command.
	// Original Task2 rate transmission is separately opt-in and restricted.
	// On Windows, IP_UNICAST_IF prevents silent use of another adapter.
	c, e := dialer.DialContext(ctx, "tcp4", addr)
	if e != nil {
		return "CONNECT_FAILED", fmt.Errorf("connect: %w", e)
	}
	defer c.Close()
	if e = verifySelectedSource(c, nic); e != nil {
		return "INTERFACE_MISMATCH", e
	}
	if m.sourceTCP!=nil {
		if e:=m.sourceTCP.begin(m);e!=nil{return "SOURCE_TCP_SEGMENT_FAILED",e}
		defer func(){m.sourceTCP.finish(m,reason)}()
	}
    // New TCP socket means a fresh original Task2 Stage0. Never
    // revive Stage1/error from a previous stream segment or earlier RUN.
    if m.sourceOriginalTask2Stage!=nil {
        m.sourceOriginalTask2Stage.onConnected(m.summary.SourceNonemptyParameters)
        defer func(){m.sourceOriginalTask2Stage.onDisconnected(reason)}()
    }
	// The original _Unit125:00807BE3 starts each socket in Stage0,
	// while _Unit125:008089D8..008089EE can queue the selected rate
	// again after a failed attempt. Do not inherit the previous socket's
	// Stage1/StatusCells0/last PARAM counter or skip its renewed SetRate.
	// This is the SAME approved TCP socket, not a second TX connection.
	if m.sourceTask2TX!=nil {
		m.sourceTask2TX.resetForNewSourceSocket(m)
		m.sourceTask2TX.conn=c
		defer func(){m.sourceTask2TX.conn=nil}()
	}
	m.summary.SocketLocalAddr = c.LocalAddr().String()
	m.summary.SocketRemoteAddr = c.RemoteAddr().String()
	m.publishLiveStatus("RECORDING", true, "")
	m.note(fmt.Sprintf("Connected TCP local=%s remote=%s (source SetRate enabled=%v)", c.LocalAddr(), c.RemoteAddr(),m.sourceTask2TX!=nil))
	fmt.Printf("TCP: %s -> %s\n", c.LocalAddr(), c.RemoteAddr())
	start := time.Now()
	lastPacket := start // source ReadTimeout=5000ms when TX approved
	// Source TMVKThread.Execute (IDP 00807A98) is terminated by the
	// operator, not by a mandatory duration. seconds==0 is an
	// explicitly approved unbounded GUI session with a hard RAW cap.
	var deadline time.Time
	if seconds > 0 { deadline = start.Add(time.Duration(seconds) * time.Second) }
	buf := make([]byte, 64*1024)
	lastPrinted := time.Time{}
	// Exactly one scanner for the full source measurement (all sockets).
	rateLines:=m.sourceOperatorRateChan
	for {
		if ctx.Err() != nil {
			return "STOPPED_BY_USER", nil
		}
		if e:=m.drainSourceOperatorRates(rateLines);e!=nil{return "SOURCE_RATE_TX_FAILED",e}
		// Source _Unit125.pas:00808769..008087B6: Task=0 transitions
		// from Stage1 (first valid nonempty PARAM) to Stage2 "Read".
		// No device command is transmitted for Task0. This is a separate
		// explicit read operation, NOT config write Task3/4/5.
		if m.sourceTask0ConfigRead && m.summary.SourceNonemptyParameters>0 && !m.captureOnly {
			return "SOURCE_TASK0_CONFIG_READ_COMPLETE",nil
		}
		if !deadline.IsZero() && !time.Now().Before(deadline) {
			return "DURATION_REACHED", nil
		}
		if m.summary.RawBytes >= maxBytes {
			return "SIZE_LIMIT_REACHED", nil
		}
		// Source _Unit125:00807E8F..00807F6A: pop and transmit exactly
		// ONE queued command before the next packet read. Never send a
		// burst from a QProcess operator callback or an RX frame callback.
		// The socket is this one already approved Task2 connection.
		if m.sourceTask2TX!=nil {
			if e:=m.sourceTask2TX.sendNext(m);e!=nil {
				return "SOURCE_RATE_TX_FAILED",e
			}
		}
		timeout := time.Now().Add(time.Second)
		if !deadline.IsZero() && timeout.After(deadline) {
			timeout = deadline
		}
		if e := c.SetReadDeadline(timeout); e != nil {
			return "READ_DEADLINE_FAILED", e
		}
		n, e := c.Read(buf)
		if n > 0 {
			lastPacket=time.Now()
			remaining := maxBytes - m.summary.RawBytes
			limit := false
			if uint64(n) > remaining {
				n = int(remaining)
				limit = true
			}
			if err := m.ProcessChunk(buf[:n], time.Now()); err != nil {
				if errors.Is(err,errTask2SourceDenied){return "SOURCE_OPERATION_DENIED",err}
				if errors.Is(err,errTask2SourceWrite){return "SOURCE_RATE_TX_FAILED",err}
                if errors.Is(err,errTask2SourceInvalidPacket){
                    return "SOURCE_INVALID_PACKET",err
                }
				return "LOCAL_WRITE_FAILED", err
			}
			m.publishLiveStatus("RECORDING", false, "")
			if m.sourceTask0ConfigRead && m.summary.SourceNonemptyParameters>0 && !m.captureOnly {
				return "SOURCE_TASK0_CONFIG_READ_COMPLETE",nil
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
				m.publishLiveStatus("RECORDING", false, "")
				if sourceOriginalReadTimedOut(lastPacket,time.Now()) {
                    // Original ReadTimeout is 5000ms for passive Task2
                    // too, not just the optional source SetRate sender.
					return "SOURCE_READ_TIMEOUT",fmt.Errorf("original TMVKThread read timeout 5000ms")
				}
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
	seconds := flag.Int("seconds", 15, "live duration 1..300 seconds, or 0 until explicit stop with -stop-file and RAW cap")
	out := flag.String("out", defaultOutput(), "root output folder")
	approve := flag.Bool("approve", false, "explicit approval to connect to industrial instrument")
	sourceTask0 := flag.Bool("source-task0-config-read",false,
		"original bConfigDownloadClick: approved read-only Task0 until first nonempty PARAM")
	sourceTX := flag.Bool("source-setrate-tx",false,"opt-in original Task2 SetRate over the SAME TCP socket; never Flash")
	sourceTXApproval := flag.Bool("source-setrate-tx-approved",false,"separate operator confirmation for hardware rate writes")
	sourceReconnect:=flag.Bool("source-task2-reconnect",false,"original Task2 retry AFTER RAW; independent SHA256 TCP segments")
	sourceReconnectApproved:=flag.Bool("source-task2-reconnect-approved",false,"separate operator consent for reconnect after live data")
	replay := flag.String("replay", "", "offline replay of captured incoming.raw (no network access)")
	limitMB := flag.Int("max-mb", 256, "maximum raw capture size in MiB (1..2048)")
	localIP := flag.String("local-ip", "", "REQUIRED for command-line live: local IPv4 of the wired Ethernet adapter")
	listIF := flag.Bool("list-interfaces", false, "show local IPv4 adapters and exit without connecting")
	stopFile := flag.String("stop-file", "", "optional absolute GUI stop-request file (.mvk_stop_requested); stops safely without killing process")
	frameMarks := flag.Bool("frame-marks", false, "opt-in local-only GUI source write boundaries; NEVER sends device commands")
	liveStatus := flag.Bool("live-status", false, "opt-in atomic local status JSON for GUI; never sends instrument data")
	autoExport := flag.Bool("export", true, "after capture, validate and atomically produce 8 BIN/TSXML + VALUES/TABLE in same run folder")
	offsetText := flag.String("offset", "auto", "capture-PC UTC offset auto or +/-HH:MM; for replay specify original capture PC timezone")
	flag.Parse()
	interactive := len(os.Args) == 1
	input := bufio.NewReader(os.Stdin)
	if *listIF {
		items, err := usableIPv4Interfaces()
		if err != nil {
			fmt.Println("Ошибка списка адаптеров:", err)
			return 2
		}
		printInterfaceChoices(items)
		return 0 // no network connection attempted
	}
	if interactive {
		defer func() { _ = interactivePrompt(input, "\nНажмите ENTER для закрытия окна: ") }()
	}
	fmt.Println("==============================================================")
	fmt.Println("     MVK Reader Web - Native TCP/10230 LIVE R6.1 / Stage108")
	if *sourceTX {
		fmt.Println("     ОРИГИНАЛЬНЫЙ TASK2 SETRATE - ОТДЕЛЬНО РАЗРЕШЁН")
	} else {
		fmt.Println("     ПАССИВНЫЙ ПРИЕМ - НИКАКИХ КОМАНД ПРИБОРУ")
	}
	fmt.Println("==============================================================")
	if *sourceTX {
		fmt.Println("SetRate(65536) и выбор пяти частот передают только 36-байтные проверенные команды, Flash/Reboot НЕ доступны.")
	} else {
		fmt.Println("Программа НЕ отправляет настройки, частоту или команду Flash.")
	}
	fmt.Println("TCP-подключение само активирует передачу МВК01, команды не нужны.")
	fmt.Println("После завершения измерения автоматический встроенный экспорт 8 BIN + TSXML + VALUES + TABLE (без дополнительного соединения).")
	fmt.Println("Для LIVE требуется явно выбрать локальный Ethernet-интерфейс.")
	fmt.Println("Сам факт TCP-подключения может влиять на прибор: нужен допуск.")
	var selectedNIC *LocalNIC
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
		items, err := usableIPv4Interfaces()
		if err != nil {
			fmt.Println("Не удалось получить интерфейсы:", err)
			return 2
		}
		selectedNIC, err = chooseNIC(input, items)
		if err != nil {
			fmt.Println("Ошибка интерфейса:", err)
			return 2
		}
		fmt.Printf("Папка результатов: %s\n", *out)
		answer := interactivePrompt(input, "Подтверждаю, что выбран Ethernet и подключение разрешено. Введите YES: ")
		*approve = strings.EqualFold(answer, "YES")
	}
	offsetMinutes, offsetErr := parseOffset(*offsetText, time.Now())
	if offsetErr != nil {
		fmt.Println("Invalid time offset:", offsetErr)
		return 2
	}
	fmt.Printf("CSV timestamp offset: %s; automatic reconstructed BIN/VALUES/TABLE: %v\n", formatOffset(offsetMinutes), *autoExport)
	if *replay != "" && *offsetText == "auto" && *autoExport {
		fmt.Println("ВНИМАНИЕ: при офлайн-повторе UTC offset берётся с ЭТОГО ПК; для исходной записи другой временной зоны используйте -offset +HH:MM.")
	}
	if *stopFile != "" {
		if e := validateStopRequestPath(*stopFile); e != nil {
			fmt.Println("Invalid stop file:", e)
			return 2
		}
	}
	if *sourceTask0 && (!*approve || *replay!="" || *autoExport ||
			*sourceTX || *sourceTXApproval || *sourceReconnect ||
			*sourceReconnectApproved || *frameMarks || !*liveStatus ||
			*stopFile=="" || *seconds<1 || *seconds>300) {
		fmt.Println("Source Task0 config reading requires approved PASSIVE TCP, bounded time, local stop; no SetRate/Flash/reboot or BIN exporter")
		return 2
	}
	if *sourceReconnect && (!*sourceReconnectApproved || !*approve || *replay!="" || !*liveStatus || *stopFile=="") {
		fmt.Println("Task2 TCP retry requires its own explicit consent, live status and local stop; SetRate approval is separate")
		return 2
	}
	if *sourceTX && (!*sourceTXApproval || !*approve || *replay!="" || !*liveStatus || *stopFile=="") {
		fmt.Println("Real source SetRate requires separate operator approval, live status and a controlled stop")
		return 2
	}
	if *frameMarks && (!*liveStatus || !*autoExport || *replay != "" || *stopFile == "") {
		fmt.Println("Local frame marks require approved GUI LIVE status, export and graceful stop")
		return 2
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
		if *seconds < 0 || *seconds > 300 {
			fmt.Println("Время должно быть 0 (до остановки) или 1..300 секунд")
			return 2
		}
		if *seconds == 0 && *stopFile == "" {
			fmt.Println("Режим до остановки требует локальный -stop-file; ограничение RAW обязательно")
			return 2
		}
		if !*approve {
			fmt.Println("Нет подтверждения разрешения на подключение; отменено без сетевых действий")
			return 2
		}
		if selectedNIC == nil {
			items, err := usableIPv4Interfaces()
			if err != nil {
				fmt.Println("Не удалось получить интерфейсы:", err)
				return 2
			}
			if *localIP == "" {
				fmt.Println("Для LIVE командной строки обязательно -local-ip <IPv4_Ethernet>. Запустите -list-interfaces для списка. Автовыбор запрещён.")
				return 2
			}
			selectedNIC, err = findNICForLocalIPv4(*localIP, items)
			if err != nil {
				fmt.Println("Ошибка интерфейса:", err)
				return 2
			}
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
	if *sourceTask0 {
		m.sourceTask0ConfigRead=true
		m.summary.Mode="LIVE_SOURCE_TASK0_CONFIG_READ_ONLY"
		fmt.Println("Original Task0: PASSIVE read of first validated PARAM. No device commands.")
	}
	if *sourceTX {
		m.summary.Mode="LIVE_SOURCE_SET_RATE_APPROVED"
		m.sourceTask2TX=newSourceLiveTask2TX()
		m.sourceTCP=&sourceTCPLedger{}
		fmt.Println("Original MVKView Task2 SetRate ENABLED with separate operator approval; only 5 verified rates")
	}
	if *sourceReconnect {
		m.sourceAfterRAWReconnect=true
		if m.sourceTCP==nil {m.sourceTCP=&sourceTCPLedger{}}
		if !*sourceTX {
			m.summary.Mode="LIVE_TASK2_PASSIVE_RECONNECT_APPROVED"
			fmt.Println("Source Task2 TCP retry approved, passive receive only: NO device SetRate")
		}
	}
	if *frameMarks {
		marks, err := newFrameMarkController(*out, dir)
		if err != nil {
			fmt.Println("Local frame mark inbox rejected:", err)
			_ = m.CloseFiles()
			return 2
		}
		m.frameMarks = marks
        // Native source writer observes actual channel frames while
        // receiving. It never relies on post-capture status snapshots
        // to guess MvkSampleRate / FreezeUpdate / first ADC1.
        m.sourceLiveDataWriter=newSourceLiveDataWriter(dir)
        m.sourceLiveValuesWriter=newSourceLiveValuesWriter(dir)
	}
	if *liveStatus {
		m.liveProgressEnabled = true
		m.liveTargetSeconds = *seconds
		m.publishLiveStatus("CONNECTING", true, "")
	}
	if *autoExport {
		if e = m.EnableLiveBinSpool(); e != nil {
			fmt.Println("Ошибка подготовки записи BIN:", e)
			_ = m.CloseFiles()
			return 2
		}
		if *liveStatus { // Explicit GUI opt-in; the accepted Native R6 BIN is unchanged.
			m.liveBin.preview = newLivePreviewBuffer()
		}
	}
	var reason string
	var runError error
    if *replay=="" && !*sourceTask0 {
        // Original _Unit128 Mode2 Create -> mRate1Click(Items[0]).
        // In passive mode we reproduce the IN-MEMORY selection 65536,
        // but NEVER transmit the real SetRate without separate consent.
        m.sourceOriginalRXGate=newSourceOriginalReceiveGate()
        m.sourceOriginalTask2Stage=newSourceOriginalTask2Lifecycle()
        // Audit source FreezeUpdate at EVERY validated PARAM boundary.
        // This journal is necessary to revalidate VALUES from unchanged
        // RAW after Stop, including skipped 0x3100 while frozen.
        gate,e:=newSourceOriginalParamGateJournal(dir)
        if e!=nil {
            fmt.Println("Cannot create source PARAM receive ledger:",e)
            _=m.CloseFiles()
            return 2
        }
        m.sourceParamGate=gate
        if m.sourceOperatorRateChan==nil {
            local:=make(chan string,16)
            m.sourceOperatorRateChan=local
            go sourceOperatorRateLines(os.Stdin,local)
        }
    }
	if *replay != "" {
		fmt.Printf("ОФЛАЙН: анализ файла %s (сеть не используется)\n", *replay)
		reason, runError = replayRaw(m, *replay, uint64(*limitMB)*1024*1024)
	} else {
		baseCtx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
		defer stop()
		ctx := baseCtx
		if *stopFile != "" {
			var cancel context.CancelFunc
			ctx, cancel = context.WithCancel(baseCtx)
			defer cancel()
			go watchStopRequest(ctx, *stopFile, cancel)
		}
		reason, runError = liveCapture(ctx, m, *ip, *seconds, uint64(*limitMB)*1024*1024, selectedNIC)
	}
	if runError != nil {
		fmt.Println("Ошибка:", runError)
		m.warn(runError.Error())
	}
	report, zipPath, finalErr := m.Finalize(reason)
	if finalErr != nil {
		m.publishLiveStatus("REFUSED", true, "FINALIZE_FAILED")
		fmt.Println("Ошибка завершения журнала:", finalErr)
		return 1
	}
	m.publishLiveStatus("VERIFYING", true, "")
	if *sourceTask0 {
		// The original bConfigDownload waits for Task0 completion, not
		// 8 ADC BIN exports. Create a local RAW-SHA-bound, redacted read
		// receipt; private Wi-Fi password and other secret register words
		// never leave the run directory or appear in logs.
		if runError!=nil || report.CaptureOnly ||
				reason!="SOURCE_TASK0_CONFIG_READ_COMPLETE" ||
				report.SourceNonemptyParameters==0 {
			m.publishLiveStatus("REFUSED",true,"SOURCE_TASK0_NOT_VERIFIED")
			fmt.Println("Task0 config not verified; original RAW remains local")
			return 1
		}
		if err:=writeSourceTask0ConfigSnapshot(m,report);err!=nil {
			m.publishLiveStatus("REFUSED",true,"SOURCE_TASK0_SNAPSHOT_FAILED")
			fmt.Println("Task0 verified RAW snapshot error:",err)
			return 1
		}
		m.publishLiveStatus("COMPLETED",true,"SOURCE_TASK0_READ_ONLY")
		fmt.Println("Task0 read-only IP config snapshot verified; no hardware writes, ZIP RAW saved")
		return 0
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
	exportStatus, exportErr := completeStage108Export(dir, report, runError, *autoExport, offsetMinutes, m.liveBin)
	if runError != nil || exportErr != nil || exportStatus.State != "EXPORTED" {
		m.publishLiveStatus("REFUSED", true, exportStatus.State)
	} else {
		m.publishLiveStatus("COMPLETED", true, exportStatus.State)
	}
	switch exportStatus.State {
	case "EXPORTED":
		fmt.Printf("Stage108: 8 BIN/TSXML + VALUES/TABLE созданы в %s (AUX=%d, VALUES=%d, конечных неполных байт исключено=%d)\n",
			filepath.Join(dir, exportStatus.OutputDir), exportStatus.AUXUpdates, exportStatus.ValuesRows, exportStatus.TerminalBytesExcluded)
	case "DISABLED":
		fmt.Println("Stage108: экспорт отключён по выбору оператора.")
	default:
		fmt.Printf("Stage108: экспорт %s: %s. Оригинальный RAW сохранён.\n", exportStatus.State, exportStatus.Error)
	}
	if report.RawBytes == 0 {
		fmt.Println("Нет входящего потока. До корректного PARAM/Status0 исходная SetRate не отправляется.")
	}
	if report.CaptureOnly {
		fmt.Println("Найден неизвестный/ошибочный кадр. Все последующие байты сохранены в incoming.raw.")
	}
	if runError != nil || exportErr != nil {
		return 1
	}
	return 0
}
func main() { os.Exit(mainInner()) }
