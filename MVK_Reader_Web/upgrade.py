from pathlib import Path
p=Path('reader_web/static/index.html')
s=p.read_text(encoding='utf8')
s=s.replace('v0.2.1 · FULL UI · локальный сервер','v0.3.4 · ONLINE TABLES · лабораторная сборка')
s=s.replace('● Только офлайн · без команд приборам','● Офлайн + Collector · только чтение')
s=s.replace('<div class="pills" id="calcTabs"></div>','<div class="flex"><label class="control">Номер прибора<select id="calcDevice"></select></label><button id="calcRefresh">Обновить данные</button></div><div class="pills" id="calcTabs"></div>')
a=s.index('async function showCalc(){')
b=s.index("$('recChannels').innerHTML",a)
new=r'''let calcDeviceList=[];
async function populateCalcDevices(){
 try{calcDeviceList=await api('/collector/api/devices');let x=$('calcDevice'),old=x.value;x.innerHTML=calcDeviceList.map(d=>`<option value="${safe(d.id)}">МВК01 №${safe(d.number)}</option>`).join('');if(calcDeviceList.some(d=>d.id===old))x.value=old;}
 catch(e){notify('Collector недоступен: '+e.message)}
}
function calcNumber(n){return typeof n==='number'&&Number.isFinite(n)?n.toFixed(4):'—'}
const calcBands=['10-3000','10-2000','10-1000','2-1000','0.62-300','0.62-150','filter1','filter2'];
const calcKinds=[['acceleration','ВУ, м/с²'],['velocity','ВС, мм/с'],['displacement','ВП, мкм']];
async function showCalc(){
 let el=$('calcBody'),id=$('calcDevice').value;
 if(!id){el.innerHTML='<div class="mutedbox">Приборы ещё не заданы на сервере.</div>';return}
 try{
 const m=await api('/collector/api/devices/'+encodeURIComponent(id)+'/measurements');
 let html=`<div class="mutedbox"><h3>${safe(calcTab)} · МВК01 №${safe(calcDeviceList.find(d=>d.id===id)?.number??id)}</h3><p>Источник: ${safe(m.source||'нет показаний')}. Получено: ${safe(m.received_at||'—')} (UTC). Статус: ${safe(m.status||'—')}.</p>`;
 const metrics={'Все каналы СКЗ':'rms','Все каналы ПИК':'peak_equivalent','Все каналы ПИК-ПИК':'peak_peak_equivalent'};
 if(metrics[calcTab]){
  let metric=metrics[calcTab];
  html+='<div style="overflow:auto"><table><tr><th>Полоса / величина</th>'+Array.from({length:8},(_,i)=>`<th>АЦП ${i+1}</th>`).join('')+'</tr>';
  for(let band of calcBands)for(let [kind,label] of calcKinds){let key=band+':'+kind;html+=`<tr><td>${safe(band)} Гц · ${label}</td>`+Array.from({length:8},(_,i)=>`<td>${calcNumber(m.channels?.find(c=>c.channel===i+1)?.[metric]?.[key]?.value)}</td>`).join('')+'</tr>'}
  html+='</table></div><p class="muted">«—» означает отсутствие реально считанного значения. ПИК и ПИК-ПИК — эквивалентные значения прибора.</p>';
 }else if(calcTab.startsWith('АЦП ')){
   let index=Number(calcTab.split(' ')[1]),c=m.channels?.find(c=>c.channel===index);
   if(!c)html+='<p>Для канала пока нет считанных регистров.</p>';
   else{
    html+=`<p>Напряжение датчика: ${calcNumber(c.voltage_v)} В; широкополосное СКЗ ускорения: ${calcNumber(c.acceleration_rms_up_to_25khz_m_s2)} м/с². Статус датчика не расшифрован.</p>`;
    html+='<div style="overflow:auto"><table><tr><th>Полоса</th><th>Величина</th><th>СКЗ</th><th>Экв. ПИК</th><th>Экв. ПИК-ПИК</th></tr>';
    for(let band of calcBands)for(let [kind,label] of calcKinds){let key=band+':'+kind;html+=`<tr><td>${safe(band)} Гц</td><td>${label}</td><td>${calcNumber(c.rms?.[key]?.value)}</td><td>${calcNumber(c.peak_equivalent?.[key]?.value)}</td><td>${calcNumber(c.peak_peak_equivalent?.[key]?.value)}</td></tr>`}
    html+='</table></div><p class="muted">Третьоктавные значения в текущем API существуют как массив без подтверждённой привязки 43 элементов к центральным частотам; до сверки с прибором график не строится.</p>';
   }
 }else if(calcTab.startsWith('Тахометр ')){
   let t=m.tachometers?.find(x=>x.channel===Number(calcTab.split(' ')[1]));
   html+=t?`<table><tr><th>Частота вращения, Гц</th><th>Приращение, Гц/оборот</th><th>Ошибка датчика (нерасшифрованное поле)</th></tr><tr><td>${calcNumber(t.frequency_hz)}</td><td>${calcNumber(t.average_frequency_increment_hz_per_rev)}</td><td>${calcNumber(t.sensor_error_raw)}</td></tr></table>`:'<p>Данные тахометра пока не получены.</p>';
 }else html+='<p>Для этого раздела ещё не подтверждена расшифровка регистров. Статус контрольных зон и системных ошибок не подменяется демонстрационными данными.</p>';
 html+='</div>';el.innerHTML=html;
 }catch(e){el.textContent='Ошибка загрузки измерений: '+e.message}
}
$('calcRefresh').onclick=async()=>{await populateCalcDevices();await showCalc()};$('calcDevice').onchange=showCalc;
populateCalcDevices().then(showCalc);
'''
s=s[:a]+new+s[b:]
s=s.replace("if(t==='wave')showWave();", "if(t==='calculated'){populateCalcDevices().then(showCalc)}if(t==='wave')showWave();")
p.write_text(s,encoding='utf8')
