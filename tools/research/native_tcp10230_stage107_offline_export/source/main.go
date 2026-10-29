package main

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
)

func prompt(in *bufio.Reader, label string) string {
	fmt.Print(label)
	s, _ := in.ReadString('\n')
	return strings.Trim(strings.TrimSpace(s), `"`)
}
func main() {
	raw := flag.String("raw", "", "path to exact Native R5/R5.1 incoming.raw")
	frames := flag.String("frames", "", "path to matching frames.csv")
	summary := flag.String("summary", "", "path to matching summary.json")
	folder := flag.String("test-dir", "", "path to folder containing incoming.raw, frames.csv, summary.json")
	output := flag.String("out", "", "NEW output directory; never overwritten")
	tz := flag.String("offset", "+00:00", "offset of capturing Windows PC clock from UTC (e.g. +07:00)")
	flag.Parse()
	interactive := *raw == "" && *frames == "" && *summary == "" && *folder == "" && *output == ""
	if interactive {
		fmt.Println("MVK Stage107 - OFFLINE 8xBIN/TSXML and VALUES/TABLE exporter")
		fmt.Println("ONLY saved test files. NO network. NO connection to MVK01. NO commands to device.")
		in := bufio.NewReader(os.Stdin)
		*folder = prompt(in, "Folder with incoming.raw, frames.csv and summary.json: ")
		if *folder == "" {
			fmt.Println("No folder provided; canceled.")
			_ = prompt(in, "Press Enter to exit...")
			return
		}
		*output = prompt(in, "NEW destination folder (Enter for <source>_EXPORTED_STAGE107): ")
		if *output == "" {
			*output = strings.TrimRight(*folder, `\\/`) + "_EXPORTED_STAGE107"
		}
		off := prompt(in, "Capture-PC UTC offset, e.g. +07:00 (Enter for +00:00): ")
		if off != "" {
			*tz = off
		}
		fmt.Println("Source folder:", *folder)
		fmt.Println("Output folder:", *output)
		fmt.Println("Time offset:", *tz)
		yes := prompt(in, "Type YES to start OFFLINE conversion (not device connection): ")
		if yes != "YES" {
			fmt.Println("Canceled")
			_ = prompt(in, "Press Enter to exit...")
			return
		}
	}
	if *folder != "" {
		if *raw != "" || *frames != "" || *summary != "" {
			fmt.Fprintln(os.Stderr, "Specify -test-dir OR all individual paths, not both.")
			os.Exit(2)
		}
		*raw = filepath.Join(*folder, "incoming.raw")
		*frames = filepath.Join(*folder, "frames.csv")
		*summary = filepath.Join(*folder, "summary.json")
	}
	if *raw == "" || *frames == "" || *summary == "" || *output == "" {
		fmt.Println("Usage: MVK_Stage107_Offline_Exporter -test-dir TEST_FOLDER -out NEW_FOLDER -offset +07:00")
		fmt.Println("Or: -raw incoming.raw -frames frames.csv -summary summary.json -out NEW_FOLDER -offset +07:00")
		fmt.Println("There are no network functions or MVK instrument commands in this program.")
		if interactive {
			_ = prompt(bufio.NewReader(os.Stdin), "Press Enter...")
		}
		os.Exit(2)
	}
	m := regexp.MustCompile(`^([+-])([0-9]{2}):([0-9]{2})$`).FindStringSubmatch(*tz)
	if m == nil {
		fmt.Fprintln(os.Stderr, "Invalid UTC offset")
		os.Exit(2)
	}
	h, _ := strconv.Atoi(m[2])
	n, _ := strconv.Atoi(m[3])
	if h > 14 || n > 59 {
		fmt.Fprintln(os.Stderr, "Invalid UTC offset range")
		os.Exit(2)
	}
	total := h*60 + n
	if m[1] == "-" {
		total = -total
	}
	rep, e := export(*raw, *frames, *summary, *output, total)
	if e != nil {
		fmt.Fprintf(os.Stderr, "FAIL CLOSED: %v\nNo valid output directory published.\n", e)
		if interactive {
			_ = prompt(bufio.NewReader(os.Stdin), "Press Enter to close window...")
		}
		os.Exit(1)
	}
	fmt.Printf("SUCCESS: %s; device=%s; frames=%d; AUX=%d; VALUES=%d; 8 BIN+TSXML\n", *output, rep.Serial, rep.FrameCount, rep.AUX, rep.ValuesRows)
	if interactive {
		_ = prompt(bufio.NewReader(os.Stdin), "Press Enter to close window...")
	}
}
