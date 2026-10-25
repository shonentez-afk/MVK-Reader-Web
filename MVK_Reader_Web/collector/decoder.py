"""Documented MVK01 register decoding (VARB.411711.112 RE, appendix 2 pp. 50-52).
Only complete register pairs are decoded. No interpolation, no fabricated readings.
"""
import math
import struct

BANDS = ['10-3000', '10-2000', '10-1000', '2-1000', '0.62-300', '0.62-150', 'filter1', 'filter2']
THIRD_OCTAVE_HZ = [0.63,0.8,1,1.25,1.6,2,2.5,3.15,4,5,6.3,8,10,12.5,16,20,25,31.5,40,50,63,80,100,125,160,200,250,315,400,500,630,800,1000,1250,1600,2000,2500,3150,4000,5000,6300,8000,10000]
KINDS = [('acceleration','m/s2'), ('velocity','mm/s'), ('displacement','um')]

def floats_from_snapshot(ranges):
    """Convert adjacent Modbus register pairs to IEEE754 float in network byte order."""
    words={}
    for row in ranges:
        for i,word in enumerate(row['values']):
            addr=row['address']+i
            if addr in words and words[addr] != word:
                raise ValueError(f'Conflicting overlapping register at {addr:#x}')
            if not isinstance(word,int) or not 0<=word<=65535: raise ValueError('Bad Modbus word')
            words[addr]=word
    def get(addr):
        if addr not in words or addr+1 not in words:return None
        v=struct.unpack('>f',struct.pack('>HH',words[addr],words[addr+1]))[0]
        return v if math.isfinite(v) else None
    return get

def decode_system(snapshot):
    """Read-only decode of documented system area 0x1000-0x1027.
    Missing register pairs yield None, never default status OK.
    """
    words={}
    for row in snapshot.get('ranges',[]):
        for i,w in enumerate(row['values']):
            a=row['address']+i
            if a in words and words[a]!=w: raise ValueError('Conflicting registers')
            words[a]=w
    def u32(addr):
        if addr not in words or addr+1 not in words:return None
        return (words[addr]<<16)|words[addr+1]
    def blob(addr,n):
        if any(a not in words for a in range(addr,addr+n//2)):return None
        return b''.join(struct.pack('>H',words[a]) for a in range(addr,addr+n//2))
    ser=blob(0x1000,8)
    raw_version=u32(0x1004)
    errors=u32(0x1006)
    error_flags=[]
    if errors is not None:
        for bit,label in [(0,'Приём данных DSP'),(1,'SD-карта: бит 1'),(2,'SD-карта: бит 2'),(3,'SD-карта: бит 3'),(4,'Отправка данных DSP'),(5,'Инициализация Modbus/TCP'),(6,'CRC конфигурации (загружена конфигурация по умолчанию)')]:
            if errors & (1<<bit):error_flags.append({'bit':bit,'label':label})
    overload=words.get(0x1020)
    return {'serial_number':ser.split(b'\0')[0].decode('cp1251',errors='replace') if ser is not None else None,
            'firmware_version': '.'.join(str((raw_version>>shift)&255) for shift in (24,16,8,0)) if raw_version is not None else None,
            'firmware_raw':raw_version,'system_errors_raw':errors,'system_error_flags':error_flags if errors is not None else None,
            'uptime_seconds':u32(0x1008),'sd_memory_kb':u32(0x100a),
            'dsp_md5_hex':blob(0x100c,16).hex() if blob(0x100c,16) is not None else None,
            'dsp_overload_channels':[i+1 for i in range(8) if overload & (1<<i)] if overload is not None else None,
            'dsp_overload_word_raw':overload,
            'source':'mvk01_modbus_fc03_system_documented',
            'notes':['Other DSP debug fields and control groups require separate register confirmation.']}

CHANNEL_STATUS_BITS = {
    0: 'Перегрузка входа',
    4: 'Буфер Fs=16 Гц не заполнен; недоступны фильтры ниже 3,9 Гц',
    5: 'Буфер Fs=64 Гц не заполнен; недоступны фильтры ниже 25 Гц',
    6: 'Буфер Fs=512 Гц не заполнен; фильтры выключены',
    10: 'Постоянное напряжение датчика выше допустимого максимума',
    11: 'Постоянное напряжение датчика не выше допустимого минимума',
}

def decode_channel_status_words(ranges, base):
    """Channel indicators A+0x120 are documented as a 4-byte float field,
    but their meaning is a BIT FIELD (manual section 3.5.7).
    Interpret raw 32 bits rather than numerical float value.
    """
    words = {}
    for row in ranges:
        for offset, word in enumerate(row['values']):
            address = row['address'] + offset
            if address in words and words[address] != word:
                raise ValueError('Conflicting overlapping register')
            words[address] = word
    a = base + 0x120
    if a not in words or a+1 not in words:
        return {'available': False, 'raw_u32': None, 'active_flags': None,
                'unrecognized_bits': None, 'interpretation': 'unknown'}
    raw = (words[a] << 16) | words[a+1]
    recognized = sum(1 << bit for bit in CHANNEL_STATUS_BITS)
    return {'available': True, 'raw_u32': raw,
            'active_flags': [{'bit': bit, 'label': label} for bit, label in CHANNEL_STATUS_BITS.items() if raw & (1 << bit)],
            'unrecognized_bits': raw & ~recognized,
            'interpretation': 'documented_bits_only'}

def decode_snapshot(snapshot):
    get=floats_from_snapshot(snapshot.get('ranges',[]))
    channels=[]
    for index in range(8):
        base=0x2000+index*0x200
        voltage=get(base)
        peak_factor=get(base+0x5c)
        wide_rms=get(base+0x5e)
        rms={}; peak={}; peak_peak={}
        for b,band in enumerate(BANDS):
            for k,(kind,unit) in enumerate(KINDS):
                i=b*3+k
                rms[f'{band}:{kind}']={'value':get(base+0x60+2*i),'unit':unit}
                peak[f'{band}:{kind}']={'value':get(base+0xa0+2*i),'unit':unit}
                peak_peak[f'{band}:{kind}']={'value':get(base+0xe0+2*i),'unit':unit}
        # Only include channel if at least one documented measurement is present.
        if voltage is not None or peak_factor is not None or wide_rms is not None or any(v['value'] is not None for v in rms.values()) or any(get(base+2+2*i) is not None for i in range(43)) or decode_channel_status_words(snapshot.get('ranges',[]),base)['available']:
            channels.append({'channel':index+1,'voltage_v':voltage,'peak_factor_acceleration':peak_factor,
                 'acceleration_rms_up_to_25khz_m_s2':wide_rms,'rms':rms,'peak_equivalent':peak,'peak_peak_equivalent':peak_peak,
                 'third_octave_acceleration_m_s2':[get(base+2+2*i) for i in range(43)],
                 'third_octave_hz':THIRD_OCTAVE_HZ,
                 'channel_status':decode_channel_status_words(snapshot.get('ranges',[]),base)})
    tachometers=[]
    for index in range(2):
        base=0x3000+index*0x100
        rpm_hz=get(base); rate=get(base+2); err=get(base+4)
        if any(v is not None for v in (rpm_hz,rate,err)):
            tachometers.append({'channel':index+1,'frequency_hz':rpm_hz,'average_frequency_increment_hz_per_rev':rate,'sensor_error_raw':err})
    return {'id':snapshot.get('id'),'received_at':snapshot.get('received_at'),'source':'mvk01_modbus_fc03_decoded',
            'channels':channels,'tachometers':tachometers,'system':decode_system(snapshot),
            'notes':['Values decoded only where complete register pairs are present.',
                     'Channel status reports only documented bit flags; other states and control zones are unknown.',
                     'Peak and peak-to-peak are device equivalent values, not waveform extrema.']}
