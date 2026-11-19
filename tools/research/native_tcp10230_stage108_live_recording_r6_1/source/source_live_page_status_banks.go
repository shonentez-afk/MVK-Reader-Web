package main

// LIVE original PageStatus raw register banks from the SINGLE already-owned
// TMVKThread-compatible receiver. The original _Unit125 constructs one
// TMvkCellList per ADC and TACH from register-word offsets. These bytes
// originate ONLY from successfully accepted PARAM, never a computed
// spectrum or a second device connection.
//
// Each nullable 8-hex-digit value encodes the original LITTLE-ENDIAN DWORD.
// A half-received DWORD MUST remain nil. Original GetValueText, alarm severity,
// RPM and Win32/x87 format parity are explicitly NOT claimed.
import "encoding/hex"

const sourceLiveResultBanksSchema="MVK_SOURCE_LIVE_PAGESTATUS_RAW_BANKS_V1"

type sourceLiveADCResultBank struct {
    ADC int `json:"adc"`
    BaseWord uint16 `json:"base_word"`
    Bands43 []*string `json:"bands_43_raw_f32_le"`
    RMS24 []*string `json:"rms_24_raw_f32_le"`
    Peak24 []*string `json:"peak_24_raw_f32_le"`
    PeakPeak24 []*string `json:"peak_peak_24_raw_f32_le"`
    SensorStatus *string `json:"sensor_status_raw_u32_le"`
    ResultADC6 []*string `json:"result_adc_six_raw_dwords_le"`
    AlarmValues []*string `json:"control_8_values_raw_f32_le"`
    AlarmStatus []*string `json:"control_8_status_raw_u32_le"`
}
type sourceLiveTachResultBank struct {
    TACH int `json:"tach"`
    BaseWord uint16 `json:"base_word"`
    Fields []*string `json:"source_field_0_2_4_6_8_fe_raw_le"`
}
type sourceLivePageStatusBanks struct {
    Schema string `json:"schema"`
    AcceptedParamFrames uint64 `json:"accepted_param_frames"`
    TCPConnectionCount uint64 `json:"tcp_connection_count"`
    GetValueTextParityVerified bool `json:"original_get_value_text_parity_verified"`
    DelphiRuntimeParityVerified bool `json:"original_delphi_runtime_parity_verified"`
    ADC []sourceLiveADCResultBank `json:"adc"`
    TACH []sourceLiveTachResultBank `json:"tach"`
}

func (m *Monitor) sourceLiveRawDWORD(addr int) *string {
    if addr<0 || addr+1>=registerWords ||
        !m.image.Valid[addr] || !m.image.Valid[addr+1] {
        return nil
    }
    raw:=hex.EncodeToString(m.image.Data[addr*2:(addr+2)*2])
    return &raw
}

func(m *Monitor) snapshotSourceLivePageStatusBanks() sourceLivePageStatusBanks {
    out:=sourceLivePageStatusBanks{
        Schema:sourceLiveResultBanksSchema,
        AcceptedParamFrames:m.summary.RegisterUpdates,
        TCPConnectionCount:m.summary.SourceTCPConnectionCount,
        ADC:make([]sourceLiveADCResultBank,8),
        TACH:make([]sourceLiveTachResultBank,2),
    }
    for ch:=0;ch<8;ch++{
        base:=0x2000+0x200*ch
        row:=sourceLiveADCResultBank{
            ADC:ch+1, BaseWord:uint16(base),
            Bands43:make([]*string,43),
            RMS24:make([]*string,24),
            Peak24:make([]*string,24),
            PeakPeak24:make([]*string,24),
            ResultADC6:make([]*string,6),
            AlarmValues:make([]*string,8),
            AlarmStatus:make([]*string,8),
        }
        for i:=0;i<43;i++{row.Bands43[i]=m.sourceLiveRawDWORD(base+2+2*i)}
        for i:=0;i<24;i++{
            row.RMS24[i]=m.sourceLiveRawDWORD(base+0x60+2*i)
            row.Peak24[i]=m.sourceLiveRawDWORD(base+0xA0+2*i)
            row.PeakPeak24[i]=m.sourceLiveRawDWORD(base+0xE0+2*i)
        }
        row.SensorStatus=m.sourceLiveRawDWORD(base+0x120)
        for i:=0;i<6;i++{
            addr,_:=sourceResultAdcSixAddress(base,i)
            row.ResultADC6[i]=m.sourceLiveRawDWORD(addr)
        }
        for j:=0;j<8;j++{
            row.AlarmValues[j]=m.sourceLiveRawDWORD(base+0x130+8*j)
            row.AlarmStatus[j]=m.sourceLiveRawDWORD(base+0x132+8*j)
        }
        out.ADC[ch]=row
    }
    for tach:=0;tach<2;tach++{
        base:=0x3000+0x100*tach
        row:=sourceLiveTachResultBank{
            TACH:tach+1,BaseWord:uint16(base),Fields:make([]*string,6),
        }
        for j,offset:=range [...]int{0,2,4,6,8,0xFE}{
            row.Fields[j]=m.sourceLiveRawDWORD(base+offset)
        }
        out.TACH[tach]=row
    }
    return out
}
