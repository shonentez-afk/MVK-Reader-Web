package main

import (
	"bytes"
	"encoding/csv"
	"errors"
	"fmt"
	"math"
	"strconv"
	"strings"
	"time"
)

// Legacy MVKView CSV files use Windows-1251, pipe separator and comma decimal.
// Encoding is kept dependency-free so this exporter cross-compiles to Windows x64.
func cp1251(s string) ([]byte, error) {
	var out []byte
	for _, r := range s {
		switch {
		case r < 128:
			out = append(out, byte(r))
		case r >= 0x0410 && r <= 0x044F:
			out = append(out, byte(r-0x0410+0xC0))
		case r == 0x0401:
			out = append(out, 0xA8)
		case r == 0x0451:
			out = append(out, 0xB8)
		case r == 0x2116:
			out = append(out, 0xB9)
		case r == 0x00AB:
			out = append(out, 0xAB)
		case r == 0x00BB:
			out = append(out, 0xBB)
		case r == 0x2013:
			out = append(out, 0x96)
		case r == 0x2014:
			out = append(out, 0x97)
		default:
			return nil, fmt.Errorf("character U+%04X is not supported in CP1251", r)
		}
	}
	return out, nil
}

func legacyCSV(rows [][]string) ([]byte, error) {
	var b bytes.Buffer
	b.WriteString("sep=|\r\n")
	w := csv.NewWriter(&b)
	w.Comma = '|'
	w.UseCRLF = true
	for _, row := range rows {
		for _, s := range row {
			if strings.ContainsAny(s, "\r\n|") {
				return nil, errors.New("CSV field contains reserved delimiter/newline")
			}
		}
		if err := w.Write(row); err != nil {
			return nil, err
		}
	}
	w.Flush()
	if err := w.Error(); err != nil {
		return nil, err
	}
	return cp1251(b.String())
}
func num(v float64) string {
	if math.IsNaN(v) || math.IsInf(v, 0) {
		return ""
	}
	if v == 0 {
		return "0"
	}
	return strings.ReplaceAll(strconv.FormatFloat(v, 'g', 4, 64), ".", ",")
}
func datetime12(t time.Time) string {
	h := t.Hour() % 12
	if h == 0 {
		h = 12
	}
	ampm := "AM"
	if t.Hour() >= 12 {
		ampm = "PM"
	}
	return fmt.Sprintf("%d/%d/%04d %d:%02d:%02d %s", int(t.Month()), t.Day(), t.Year(), h, t.Minute(), t.Second(), ampm)
}
func tsxml(filename string, ch int, serial string, rate uint32, gain float32, n uint64, ended time.Time) ([]byte, error) {
	if ch < 0 || ch >= 8 || n == 0 || rate == 0 {
		return nil, errors.New("invalid TSXML channel/count/rate")
	}
	if !finiteF32(gain) || gain <= 0 {
		return nil, errors.New("gain must be valid")
	}
	to := float64(n) * 1000.0 / float64(rate)
	// Exact structure and field order observed in four original MVKView TSXML.
	x := fmt.Sprintf("<?xml version=\"1.0\" encoding=\"windows-1251\"?>\r\n<MainRoot>\r\n"+
		"<DateTime>%s</DateTime>\r\n<Culture>en-US</Culture>\r\n<From Units=\"ms\">0</From>\r\n"+
		"<To Units=\"ms\">%.2f</To>\r\n<ChannelsQuantity>1</ChannelsQuantity>\r\n"+
		"<FrequencyPerChannel>%d</FrequencyPerChannel>\r\n<DataFileName>.\\%s</DataFileName>\r\n"+
		"<Channels>\r\n  <Channel Index=\"0\">\r\n    <ChannelName>%s-ADC%d</ChannelName>\r\n"+
		"    <ChannelNumber>%d</ChannelNumber>\r\n    <ChannelFrequency>%d</ChannelFrequency>\r\n"+
		"    <Units>м/с2</Units>\r\n    <RealDataType>Single</RealDataType>\r\n"+
		"    <DataLength>%d</DataLength>\r\n    <DataOffset>0</DataOffset>\r\n"+
		"    <InternalChannelGain>%s</InternalChannelGain>\r\n  </Channel>\r\n</Channels>\r\n</MainRoot>\r\n",
		datetime12(ended), to, rate, filename, serial, ch+1, ch+1, rate, n*4, strconv.FormatFloat(float64(gain), 'g', 9, 64))
	return cp1251(x)
}

func buildValuesRows(ticks []snapshot, offset int) [][]string {
	headers := make([]string, 1, 1+8*73)
	titles := make([]string, 1, 1+8*73)
	headers[0] = ""
	titles[0] = "Время"
	for ch := 0; ch < 8; ch++ {
		for _, l := range valuesLabels {
			headers = append(headers, fmt.Sprintf("АЦП %d", ch+1))
			titles = append(titles, l)
		}
	}
	rows := [][]string{headers, titles}
	tz := time.FixedZone("operator capture offset", offset*60)
	for _, t := range ticks {
		if t.TickTimeUTC == "" {
			panic("internal missing timestamp")
		}
		d, err := time.Parse(time.RFC3339Nano, t.TickTimeUTC)
		if err != nil {
			panic("validated frame UTC became invalid")
		}
		row := make([]string, 0, 1+8*73)
		row = append(row, d.In(tz).Format("15:04:05.000"))
		for c := 0; c < 8; c++ {
			row = append(row, t.Data[c].CSVFields(c, t.DSPStatus)...)
		}
		rows = append(rows, row)
	}
	return rows
}

// CSVFields uses the exact 73-column order from a real MVKView VALUES export:
// 43 third-octaves; 3 status cells; sensor voltage; X..25k; crest; 24 band RMS.
// Fault text is explicitly *not* assumed to match MVKView's localized UI.
func (c channelSnap) CSVFields(channel int, dsp uint32) []string {
	out := make([]string, 0, 73)
	for _, v := range c.Third {
		out = append(out, num(v))
	}
	overload := "ОК"
	if dsp&(uint32(1)<<uint(channel)) != 0 {
		overload = "1"
	}
	buffer := "ОК"
	if c.Status&0x70 != 0 {
		buffer = fmt.Sprintf("0x%08X", c.Status&0x70)
	}
	sensor := "ОК"
	if c.Status&0xC00 != 0 {
		sensor = fmt.Sprintf("0x%08X", c.Status&0xC00)
	}
	out = append(out, overload, buffer, sensor, num(c.Voltage), num(c.Accel25k), num(c.Crest))
	for _, v := range c.RMS {
		out = append(out, num(v))
	}
	if len(out) != 73 {
		panic("internal MVKView field map not 73")
	}
	return out
}
func buildTableRows(s snapshot) [][]string {
	title := []string{"Наименование параметра"}
	for ch := 0; ch < 8; ch++ {
		title = append(title, fmt.Sprintf("АЦП %d", ch+1))
	}
	title = append(title, "")
	rows := [][]string{title}
	for n := 0; n < 30; n++ {
		label := ""
		unit := ""
		switch n {
		case 0:
			label = "Индикатор перегрузки"
		case 1:
			label = "Индикатор заполнения буферов"
		case 2:
			label = "Состояние датчика"
		case 3:
			label = "Напряжение на датчике"
			unit = "В"
		default:
			label = tableMeasureLabels[n-4]
			unit = tableUnits[n-4]
		}
		row := []string{label}
		for ch := 0; ch < 8; ch++ {
			row = append(row, s.Data[ch].CSVFields(ch, s.DSPStatus)[43+n])
		}
		row = append(row, unit)
		rows = append(rows, row)
	}
	rows = append(rows, []string{})
	rows = append(rows, []string{"Наименование параметра", "Тахометр 1", "Тахометр 2", "Ед."})
	labels := []string{"Частота вращения", "Среднее приращение ЧВ на один оборот", "Ошибка датчика оборотов", "Последняя метка времени", "Текущее значение на входе", "Наличие импульсов на входе"}
	units := []string{"Гц", "Гц", "", "1/65536 с", "", ""}
	for i, l := range labels {
		row := []string{l}
		for ch := 0; ch < 2; ch++ {
			if i < 2 {
				row = append(row, num(s.TachF[ch][i]))
			} else if i < 5 {
				row = append(row, strconv.FormatUint(uint64(s.TachU[ch][i-2]), 10))
			} else {
				row = append(row, "")
			}
		}
		row = append(row, units[i])
		rows = append(rows, row)
	}
	return rows
}