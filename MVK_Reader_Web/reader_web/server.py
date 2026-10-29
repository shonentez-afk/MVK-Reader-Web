"""MVK Reader Web 0.2: file-only offline viewer. No instrument networking."""
from pathlib import Path
import csv, io, json, os, sqlite3, shutil, uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, File, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import numpy as np
from mvk_core import load_recording, metrics, compute_spectrum, spectrum_metrics, downsample_for_plot

ROOT=Path(__file__).resolve().parent
DATA=Path(os.getenv('MVK_DATA_DIR',str(ROOT/'data'))).resolve()
DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'archive.sqlite3'
MAX_BIN=150*1024*1024
MAX_XML=1024*1024
app=FastAPI(title='MVK Reader Web',version='0.2.1',description='Только локальные файлы. Нет драйвера и команд для прибора.')
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')

@contextmanager
def db():
    con=sqlite3.connect(DB)
    try:
        con.execute('CREATE TABLE IF NOT EXISTS recordings (id TEXT PRIMARY KEY, name TEXT NOT NULL, added TEXT NOT NULL, fs REAL NOT NULL, duration REAL NOT NULL, channel TEXT NOT NULL, count INTEGER NOT NULL)')
        con.commit()
        yield con
    finally: con.close()

with db(): pass

def get_record(rid):
    with db() as con: row=con.execute('SELECT id,name,added,fs,duration,channel,count FROM recordings WHERE id=?',(rid,)).fetchone()
    if row is None: raise HTTPException(404,'Запись не найдена')
    return dict(zip(('id','name','added','fs','duration','channel','count'),row))

def load(rid):
    rec=get_record(rid)
    try: recording=load_recording(DATA/rid/'record.bin')
    except (ValueError,OSError,KeyError) as exc: raise HTTPException(422,str(exc)) from exc
    return rec,recording

async def save_upload(upload:UploadFile,path:Path,max_size:int):
    total=0
    with path.open('wb') as f:
        while chunk:=await upload.read(1024*1024):
            total+=len(chunk)
            if total>max_size: raise HTTPException(413,'Файл слишком большой')
            f.write(chunk)
    if not total: raise HTTPException(422,'Пустой файл')

@app.get('/')
def index():return FileResponse(ROOT/'static'/'index.html')

@app.get('/api/health')
def health():return {'status':'ok','version':'0.2.1','mode':'offline-only','device_commands_enabled':False}

@app.get('/api/recordings')
def list_records():
    with db() as con:rows=con.execute('SELECT id,name,added,fs,duration,channel,count FROM recordings ORDER BY added DESC').fetchall()
    return [dict(zip(('id','name','added','fs','duration','channel','count'),r)) for r in rows]

@app.post('/api/recordings',status_code=201)
async def upload_recording(binary:UploadFile=File(...),description:UploadFile=File(...)):
    if not (binary.filename or '').lower().endswith('.bin') or not (description.filename or '').lower().endswith('.tsxml'):
        raise HTTPException(422,'Требуются .bin и .tsxml')
    rid=uuid.uuid4().hex
    folder=DATA/rid;folder.mkdir()
    try:
        await save_upload(binary,folder/'record.bin',MAX_BIN)
        await save_upload(description,folder/'record.bin.tsxml',MAX_XML)
        r=load_recording(folder/'record.bin')
        name=Path(binary.filename).name[:240]
        row=(rid,name,datetime.now(timezone.utc).isoformat(),float(r.fs),float(r.duration),str(r.channel),len(r.samples))
        with db() as con:
            con.execute('INSERT INTO recordings VALUES (?,?,?,?,?,?,?)',row);con.commit()
        return dict(zip(('id','name','added','fs','duration','channel','count'),row))
    except (ValueError, OSError, KeyError) as exc:
        shutil.rmtree(folder,ignore_errors=True)
        raise HTTPException(422, str(exc)) from exc
    except Exception:
        shutil.rmtree(folder,ignore_errors=True)
        raise

@app.delete('/api/recordings/{rid}')
def delete_record(rid:str):
    get_record(rid)
    with db() as con:con.execute('DELETE FROM recordings WHERE id=?',(rid,));con.commit()
    shutil.rmtree(DATA/rid,ignore_errors=True)
    return {'deleted':rid}

@app.get('/api/recordings/{rid}')
def record_details(rid:str):
    info,r=load(rid)
    return {**info,'unit':r.units,'started':r.started,'gain_metadata':r.gain_metadata,'metrics':metrics(r.samples)}

@app.get('/api/recordings/{rid}/waveform')
def waveform(rid:str,mode:str=Query('ac',pattern='^(ac|acdc)$'),start:float=Query(0,ge=0),seconds:float=Query(0,ge=0,le=120),points:int=Query(5000,ge=200,le=15000)):
    _,r=load(rid)
    a=min(len(r.samples),int(start*r.fs))
    b=min(len(r.samples), a+int(seconds*r.fs)) if seconds else len(r.samples)
    if a>=b: raise HTTPException(422,'Участок времени за пределами записи')
    x=np.asarray(r.samples[a:b],dtype=np.float64)
    if mode=='ac':x=x-np.mean(r.samples,dtype=np.float64)
    t,y=downsample_for_plot(x,r.fs,points)
    return {'time_s':(t+a/r.fs).tolist(),'amplitude':y.tolist(),'unit':r.units,'mode':mode,'start':start,'duration':(b-a)/r.fs}

def calculate_spectrum(rid,kind,df,lo,hi):
    if kind not in ('acceleration','velocity','displacement'):raise HTTPException(422,'Неизвестный тип спектра')
    _,r=load(rid)
    if hi>r.fs/2:hi=r.fs/2
    if hi<=lo:raise HTTPException(422,'Некорректная полоса частот')
    f,y,unit=compute_spectrum(r.samples,r.fs,df=df,kind=kind)
    mask=(f>=lo)&(f<=hi)
    if not np.any(mask):raise HTTPException(422,'Пустой диапазон')
    return f[mask],y[mask],unit,spectrum_metrics(f,y,lo=lo,hi=hi)

def apply_spectrum_band(f,y,filter_id):
    if filter_id=='none': return y
    try:
        prefix,width,center=filter_id.split(':')
        if prefix!='oct': raise ValueError()
        width=float(width);center=float(center)
        if width<=0 or center<=0: raise ValueError()
    except (ValueError,TypeError) as exc: raise HTTPException(422,'Некорректный фильтр') from exc
    low=center/2**(width/2);high=center*2**(width/2)
    return np.where((f>=low)&(f<=high),y,0.0)

def exported_spectrum(rid,kind,df,lo,hi,filter_id='none'):
    f,a,unit,_=calculate_spectrum(rid,kind,df,lo,hi)
    a=apply_spectrum_band(f,a,filter_id)
    return f,a,unit,{'spectrum_rms':float(np.linalg.norm(a)),
                     'peak_frequency_hz':float(f[np.argmax(a)]),
                     'peak_rms':float(np.max(a))}

@app.get('/api/recordings/{rid}/spectrum')
def spectrum(rid:str,kind:str='velocity',df:float=Query(.25,ge=.25,le=8),lo:float=Query(1,ge=1),hi:float=Query(100,gt=1),filter_id:str='none',points:int=Query(4000,ge=400,le=25000)):
    f,y,unit,m=calculate_spectrum(rid,kind,df,lo,hi)
    y=apply_spectrum_band(f,y,filter_id)
    m={'spectrum_rms':float(np.linalg.norm(y)), 'peak_frequency_hz':float(f[np.argmax(y)]), 'peak_rms':float(np.max(y))}
    if len(f)>points:
        idx=np.linspace(0,len(f)-1,points,dtype=int)
        peak=np.argmax(y)
        idx=np.unique(np.concatenate((idx,[peak])))
        f,y=f[idx],y[idx]
    return {'frequency_hz':f.tolist(),'amplitude':y.tolist(),'unit':unit,'metrics':m,'filter_id':filter_id,'note':'Оценка Welch/Hann; методика MVKView пока не воспроизведена точно'}

@app.get('/api/recordings/{rid}/spectrum.csv')
def spectrum_csv(rid:str,kind:str='velocity',df:float=Query(.25,ge=.25,le=8),lo:float=Query(1,ge=1),hi:float=Query(100,gt=1),filter_id:str='none'):
    f,y,unit,_=exported_spectrum(rid,kind,df,lo,hi,filter_id)
    output=io.StringIO();w=csv.writer(output);w.writerow(['frequency_hz',f'amplitude ({unit})'])
    w.writerows(zip(f,y))
    payload=output.getvalue().encode('utf-8-sig')
    return StreamingResponse(iter([payload]),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="spectrum.csv"'})

@app.get('/api/recordings/{rid}/report.json')
def report_json(rid:str,kind:str='velocity',df:float=Query(.25,ge=.25,le=8),lo:float=Query(1,ge=1),hi:float=Query(100,gt=1),filter_id:str='none'):
    info,r=load(rid);_,_,unit,m=exported_spectrum(rid,kind,df,lo,hi,filter_id)
    result={**info,'units':r.units,'started':r.started,'signal_metrics':metrics(r.samples),'spectrum_metrics':m,'spectrum_unit':unit,'spectrum_filter_id':filter_id,'spectrum_method':'Welch, Hann, no overlap; not validated for metrological conformity'}
    return result

@app.get('/api/recordings/{rid}/download/{part}')
def download_original(rid:str,part:str):
    if part not in ('bin','tsxml'):raise HTTPException(404)
    info=get_record(rid)
    path=DATA/rid/('record.bin' if part=='bin' else 'record.bin.tsxml')
    return FileResponse(path,filename=info['name']+('.tsxml' if part=='tsxml' else ''))


# FULL UI additions: read-only offline archive, reports and analysis. No device network.
from fastapi import Body
from fastapi.responses import Response
from scipy import signal as scipy_signal

THIRD_OCTAVE = [0.63,0.8,1,1.25,1.6,2,2.5,3.15,4,5,6.3,8,10,12.5,16,20,25,31.5,40,50,63,80,100,125,160,200,250,315,400,500,630,800,1000,1250,1600,2000,2500,3150,4000,5000,6300,8000,10000,12500,16000,20000,25000]
FILTER_OPTIONS = [{'id':'none','label':'Без фильтра'}]+[{'id':f'oct:{w}:{f}','label':f'{w} окт · {f:g} Гц'} for w,centers in [(1/3,THIRD_OCTAVE),(1,[0.5,1,2,4,8,16,31.5,63,125,250,500,1000,2000,4000,8000,16000]),(2,[0.5,1,2,4,8,16,31.5,63,125,250,500,1000,2000,4000,8000,13000])] for f in centers]
WINDOWS_MS=[20000,10000,5000,2000,1000,500,200,100,50,20,10,5,2,1]
RESOLUTIONS=[.25,.5,1,2,4,8]
FREQUENCY_LIMITS=[50,100,200,400,800,1600,3200,6400,12800,25600]

@app.get('/api/capabilities')
def capabilities():
    return {'mode':'offline-only','modbus_enabled':False,'device_commands_enabled':False,'instrument_data_available':False,
            'filters':FILTER_OPTIONS,'windows_ms':WINDOWS_MS,'resolutions_hz':RESOLUTIONS,'frequency_limits_hz':FREQUENCY_LIMITS,
            'channels':['АЦП '+str(i) for i in range(1,9)]+['Тахометр 1','Тахометр 2'],
            'signal_types':['AC','AC+DC'],'spectrum_types':['acceleration','velocity','displacement'],
            'limits':'Без приборного соединения; тахометры и диагностические значения требуют онлайн-данных'}

def filtered_signal(r,filter_id='none',start=0,seconds=0):
    a=int(start*r.fs); b=min(len(r.samples),a+int(seconds*r.fs)) if seconds else len(r.samples)
    if a>=b or a<0:raise HTTPException(422,'Участок вне записи')
    x=np.asarray(r.samples[a:b],dtype=np.float64)
    if filter_id=='none':return x
    try:
        _,width,center=filter_id.split(':'); width=float(width);center=float(center)
    except Exception as exc:raise HTTPException(422,'Неверный фильтр') from exc
    low=center/(2**(width/2));high=center*(2**(width/2)); ny=r.fs/2
    if low<=0 or high>=ny:raise HTTPException(422,'Полоса фильтра за пределами Найквиста')
    if len(x)<128:raise HTTPException(422,'Для фильтра слишком короткий сигнал')
    sos=scipy_signal.butter(4,[low,high],btype='bandpass',fs=r.fs,output='sos')
    return scipy_signal.sosfiltfilt(sos,x)

@app.get('/api/recordings/{rid}/waveform-plus')
def waveform_plus(rid:str,mode:str=Query('ac',pattern='^(ac|acdc)$'),filter_id:str='none',start:float=Query(0,ge=0),seconds:float=Query(0,ge=0,le=120),points:int=Query(5000,ge=200,le=15000)):
    _,r=load(rid)
    x=filtered_signal(r,filter_id,start,seconds)
    if mode=='ac': x=x-np.mean(x)
    t,y=downsample_for_plot(x,r.fs,points)
    return {'time_s':(t+start).tolist(),'amplitude':y.tolist(),'unit':r.units,'mode':mode,
            'metrics':{'rms':float(np.sqrt(np.mean(x*x))),'peak':float(np.max(np.abs(x))),'mean':float(np.mean(x))},
            'duration':len(x)/r.fs,'note':'Фильтрация Butterworth 4-го порядка, не утверждена как идентичная MVKView'}

@app.get('/api/recordings/{rid}/third-octave')
def third_octave(rid:str,kind:str='acceleration'):
    if kind not in ('acceleration','velocity','displacement'):raise HTTPException(422,'Неизвестный тип')
    _,r=load(rid)
    f,a,unit=compute_spectrum(r.samples,r.fs,df=.25,kind=kind)
    values=[]
    for center in THIRD_OCTAVE:
        low=center*2**(-1/6);high=center*2**(1/6)
        mask=(f>=low)&(f<high)
        if high>=r.fs/2:continue
        values.append({'center_hz':center,'rms':float(np.linalg.norm(a[mask]))})
    return {'unit':unit,'bands':values,'note':'Оценка по интегрированию FFT-bin; не метрологический третьоктавный фильтр МВК01'}

@app.get('/api/recordings/{rid}/summary')
def offline_summary(rid:str):
    rec,r=load(rid)
    return {'recording':rec,'metadata':{'units':r.units,'started':r.started,'gain':r.gain_metadata},
            'signal':metrics(r.samples),'channels':[{'name':r.channel,'available':True,'source':'BIN/TSXML'}],
            'online_calculated_values_available':False,'warnings':['Из BIN нельзя восстановить состояние датчиков, контрольные зоны и Modbus-показатели','Метод FFT требует сопоставления с оригиналом']}

@app.get('/api/recordings/{rid}/report.xlsx')
def report_xlsx(rid:str,kind:str='velocity',df:float=Query(.25,ge=.25,le=8),lo:float=Query(1,ge=1),hi:float=Query(100,gt=1),filter_id:str='none'):
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment
    rec,r=load(rid);f,a,unit,sm=exported_spectrum(rid,kind,df,lo,hi,filter_id)
    book=Workbook();ws=book.active;ws.title='Сводка'
    rows=[['MVK Reader · отчёт по записи',''],['Файл',rec['name']],['Канал',r.channel],['Дата измерения',r.started],['Частота дискретизации, Гц',r.fs],['Длительность, с',r.duration],['Ед. изм.',r.units],['Спектр',kind],['Фильтр',filter_id],['Диапазон, Гц',f'{lo}–{hi}'],['Частота пика, Гц',sm['peak_frequency_hz']],['Амплитуда пика',sm['peak_rms']],['СКЗ спектра',sm['spectrum_rms']],['Важное замечание','Расчёты не поверены и не идентичны MVKView']]
    for row in rows:ws.append(row)
    ws.column_dimensions['A'].width=40;ws.column_dimensions['B'].width=74
    for cell in ws[1]:cell.font=Font(bold=True,color='FFFFFF',size=14);cell.fill=PatternFill('solid',fgColor='18394C')
    sw=book.create_sheet('Спектр');sw.append(['Частота, Гц',f'Амплитуда, {unit}'])
    for q,v in zip(f,a):sw.append([float(q),float(v)])
    sw.column_dimensions['A'].width=24;sw.column_dimensions['B'].width=25
    for c in sw[1]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='18394C')
    bio=io.BytesIO();book.save(bio)
    return Response(content=bio.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename="mvk_report.xlsx"'})

@app.get('/api/recordings/{rid}/report.pdf')
def report_pdf(rid:str,kind:str='velocity',df:float=Query(.25,ge=.25,le=8),lo:float=Query(1,ge=1),hi:float=Query(100,gt=1),filter_id:str='none'):
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    rec,r=load(rid);f,a,unit,sm=exported_spectrum(rid,kind,df,lo,hi,filter_id)
    buf=io.BytesIO();c=canvas.Canvas(buf,pagesize=(595,842))
    font_file=next((str(q) for q in [Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'arial.ttf'] if q.exists()),'')
    if os.path.exists(font_file):pdfmetrics.registerFont(TTFont('MVKDejaVu',font_file));font='MVKDejaVu'
    else:font='Helvetica'
    c.setFont(font,17);c.drawString(35,795,'MVK Reader · отчёт измерения')
    c.setFont(font,9)
    lines=[('Файл',rec['name'][:78]),('Канал',r.channel),('Дата записи',r.started),('Частота дискретизации',f'{r.fs:g} Гц'),('Длительность',f'{r.duration:.6f} с'),('Метод','Welch / Hann (оценочный)'),('Фильтр',filter_id),('Полоса анализа',f'{lo:g}–{hi:g} Гц'),('Основной пик',f'{sm["peak_frequency_hz"]:.3f} Гц'),('Амплитуда пика',f'{sm["peak_rms"]:.5f} {unit}'),('СКЗ спектра',f'{sm["spectrum_rms"]:.5f} {unit}')]
    y=744
    for key,val in lines:c.drawString(35,y,f'{key}: {val}');y-=22
    c.setFont(font,9);c.drawString(35,y-20,'Спектр измерения (доступный диапазон)')
    from reportlab.lib.colors import HexColor
    px,py,pw,ph=48,290,500,180
    c.setStrokeColor(HexColor('#BECBD8'));c.rect(px,py,pw,ph,stroke=1,fill=0)
    vmax=float(np.max(a)) if len(a) else 1;vmax=max(vmax,1e-10)
    stride=max(1,len(f)//1500)
    path=c.beginPath()
    for i in range(0,len(f),stride):
        xx=px+pw*(f[i]-f[0])/max(f[-1]-f[0],1e-8);yy=py+ph*a[i]/vmax
        if i==0:path.moveTo(xx,yy)
        else:path.lineTo(xx,yy)
    c.setStrokeColor(HexColor('#047FA3'));c.drawPath(path)
    c.setFillColor(HexColor('#9B4C17'));c.setFont(font,8)
    c.drawString(35,255,'НЕ ПОВЕРЕНО: результаты расчётов пока не эквивалентны MVKView.')
    c.drawString(35,240,'Отчёт построен офлайн из сохранённого BIN/TSXML; нет данных о состоянии прибора.')
    c.save()
    return Response(content=buf.getvalue(),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="mvk_report.pdf"'})


# Stage110 ORIGINAL MVKView tabs — explicitly enabled research-only UI.
# Default OFF; does not connect to devices or modify verified Native R6.1.
if os.getenv('MVK_STAGE110_ENABLE', '0') == '1':
    from stage110_original_tabs import router as _mvk_stage110_router
    app.include_router(_mvk_stage110_router)

    @app.get('/stage110/', include_in_schema=False)
    def stage110_original_mvkview_tabs():
        return FileResponse(ROOT / 'static' / 'stage110_original_tabs.html')
