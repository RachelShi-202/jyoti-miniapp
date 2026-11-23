'use strict';
(()=>{
 const zodiac=['白羊','金牛','双子','巨蟹','狮子','处女','天秤','天蝎','射手','摩羯','水瓶','双鱼'];
 const cells=[[1,2],[1,3],[1,4],[2,4],[3,4],[4,4],[4,3],[4,2],[4,1],[3,1],[2,1],[1,1]];
 let loadedSession='',cache=new Map(),currentView='natal';
 const dateText=value=>new Intl.DateTimeFormat('zh-CN',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value));
 const dayText=value=>new Intl.DateTimeFormat('zh-CN',{month:'short',day:'numeric'}).format(new Date(value));
 const unique=items=>[...new Set(items.filter(Boolean))];

 function createShell(){
  if(!document.querySelector('link[href*="timing.css"]')){const link=document.createElement('link');link.rel='stylesheet';link.href='/static/timing.css?v=20261112-timing-v1';document.head.append(link)}
  if($('#timing-lab'))return;
  const shell=node('section',undefined,'timing-lab');shell.id='timing-lab';
  const head=node('div',undefined,'timing-head'),copy=node('div');copy.append(node('span','ANNUAL TIMING','eyebrow'),node('h2','年度独立盘 · 双轨月历'));head.append(copy,node('span','新增','badge'));
  shell.append(head,node('p','以年度太阳返照盘为独立盘面，同时交叉本命三级运、年度 Mudda 与太阳换座。仅展示计算时间，不自动判断事件吉凶。','hint'));
  const controls=node('div',undefined,'timing-controls'),label=node('label','查看年份');const input=node('input');input.id='timing-year';input.type='number';input.min='1900';input.max='2100';label.append(input);const button=node('button','生成年度时间图谱','secondary');button.id='timing-load';button.type='button';controls.append(label,button);shell.append(controls);
  const status=node('p','先选择年份，再生成年度独立盘。','hint');status.id='timing-status';status.setAttribute('role','status');shell.append(status);
  const content=node('div');content.id='timing-content';content.hidden=true;
  const summary=node('div',undefined,'timing-summary');summary.id='timing-summary';content.append(summary);
  content.append(panel('Varshaphala · 年度返照独立盘','annual-panel'),panel('双轨月历 · 交叉时间','track-panel'),panel('Sankranti · 太阳每月换座日历','sankranti-panel'));
  content.querySelector('#annual-panel').append(Object.assign(node('div',undefined,'chart-grid annual-chart-grid'),{id:'annual-chart-grid'}),Object.assign(node('div'),{id:'annual-planet-list'}));
  const legend=node('div',undefined,'track-legend');legend.append(node('span','本命轨：大运 / 小运 / 三级运'),node('span','年度轨：Mudda'));content.querySelector('#track-panel').append(legend,Object.assign(node('div'),{id:'dual-track-months'}));
  content.querySelector('#sankranti-panel').append(Object.assign(node('div'),{id:'sankranti-list'}));
  shell.append(content);shell.hidden=true;
  const switcher=node('div',undefined,'chart-view-switch segmented');switcher.setAttribute('aria-label','切换本命盘与年度独立盘');
  const natalButton=node('button','本命盘','selected'),annualButton=node('button','年度独立盘');natalButton.type=annualButton.type='button';natalButton.id='show-natal-chart';annualButton.id='show-annual-chart';switcher.append(natalButton,annualButton);
  $('#varga-picker').before(switcher);switcher.after(shell);button.onclick=()=>busy(button,loadTiming);natalButton.onclick=()=>setChartView('natal');annualButton.onclick=()=>setChartView('annual');
 }
 function setChartView(view){
  currentView=view;const annual=view==='annual';
  for(const selector of ['#varga-picker','#varga-guide','#diagram','#chart-note','#positions-title','#planet-list','#period-panel']){const item=$(selector);if(item)item.hidden=annual}
  $('#timing-lab').hidden=!annual;$('#show-natal-chart').classList.toggle('selected',!annual);$('#show-annual-chart').classList.toggle('selected',annual);$('#show-natal-chart').setAttribute('aria-pressed',String(!annual));$('#show-annual-chart').setAttribute('aria-pressed',String(annual));
  if(annual&&active&&active.chart.status==='calculated'&&$('#timing-content').hidden)busy($('#timing-load'),loadTiming);
 }
 function panel(title,id){const details=node('details',undefined,'card timing-panel');details.id=id;details.open=id!=='sankranti-panel';details.append(node('summary',title));return details}
 function stat(label,value){const box=node('div',undefined,'timing-stat');box.append(node('small',label),node('b',value));return box}

 function renderAnnual(result){
  const yearly=result.varshaphala,chart=yearly.chart,muntha=yearly.muntha,mudda=yearly.muddaDasha;
  $('#timing-summary').replaceChildren(stat('年度起点',dateText(yearly.returnLocal)),stat('年度上升',chart.ascendant.sign),stat('Muntha',`${muntha.sign} · 第${muntha.house}宫`),stat('起始 Mudda',mudda.startingLord));
  const grid=$('#annual-chart-grid');grid.replaceChildren();zodiac.forEach((sign,i)=>{const box=node('div',sign,'cell');box.style.gridArea=`${cells[i][0]}/${cells[i][1]}`;if(chart.ascendant.signIndex===i)box.append(node('b','↑ 年度上升'));if(muntha.signIndex===i)box.append(node('b','◆ Muntha'));chart.planets.filter(p=>p.signIndex===i).forEach(p=>box.append(node('b',p.name)));grid.append(box)});const center=node('div',undefined,'center');center.append(node('strong','✧'),node('span',`${yearly.year} 年返照盘`),node('span',`上升 · ${chart.ascendant.sign}`));grid.append(center);
  $('#annual-planet-list').replaceChildren(...chart.planets.map(p=>{const row=node('div',undefined,'row');row.append(node('span',p.name+(p.retrograde?' ℞':'')),node('span',`${p.sign} ${p.degree.toFixed(2)}° · 第${p.house}宫`));return row}));
 }
 function groupSolarMonths(windows){const groups=[];for(const item of windows){let group=groups.at(-1);if(!group||group.sign!==item.sunSign||group.end!==item.start){group={sign:item.sunSign,start:item.start,end:item.end,natal:[],mudda:[]};groups.push(group)}group.end=item.end;if(item.natalTrack)group.natal.push(`${item.natalTrack.mahadasha} / ${item.natalTrack.antardasha} / ${item.natalTrack.pratyantardasha}`);if(item.annualTrack)group.mudda.push(item.annualTrack.muddaLord)}return groups}
 function renderTracks(result){
  const box=$('#dual-track-months');box.replaceChildren();groupSolarMonths(result.crossWindows).forEach((month,index)=>{const details=node('details',undefined,'track-month');if(index===0)details.open=true;const summary=node('summary');summary.append(node('b',month.sign+'太阳月'),node('small',`${dayText(month.start)} → ${dayText(month.end)}`));details.append(summary);const natal=node('div',undefined,'track-line natal-track');natal.append(node('span','本命轨'),node('p',unique(month.natal).join('\n')));const annual=node('div',undefined,'track-line annual-track');annual.append(node('span','年度轨'),node('p',unique(month.mudda).map(x=>x+' Mudda').join(' → ')));details.append(natal,annual);box.append(details)});
 }
 function renderSankranti(result){
  $('#sankranti-list').replaceChildren(...result.sankrantiCalendar.events.map(item=>{const row=node('div',undefined,'sankranti-row');const copy=node('span');copy.append(node('b',`${item.fromSign} → ${item.sign}`),node('small',dateText(item.local)));row.append(copy,node('em',`${item.targetLongitude}°`));return row}));
 }
 function renderResult(result){renderAnnual(result);renderTracks(result);renderSankranti(result);$('#timing-content').hidden=false;$('#timing-status').textContent=`${result.year} 年度时间图谱已生成 · ${result.pratyantardashas.length} 段三级运交叉`}
 async function loadTiming(){
  if(!active||!session)throw Error('请先生成或打开一张已保存的星盘');const year=Number($('#timing-year').value);if(!Number.isInteger(year)||year<1900||year>2100)throw Error('请选择1900—2100之间的年份');const key=session+':'+year;$('#timing-status').textContent='正在计算太阳返照、三级运与换座时间…';const result=cache.get(key)||await api('timing/'+year,null,{'X-Jyoti-Session':session});cache.set(key,result);renderResult(result);
 }
 window.renderTimingOverview=()=>{createShell();if(!active)return;if(loadedSession!==session){loadedSession=session;cache=new Map();$('#timing-content').hidden=true;$('#timing-status').textContent=active.chart.status==='calculated'?'点击“年度独立盘”即可生成当前年度盘面。':'估计时刻不能生成年度返照盘，请使用准确出生时刻。'}const year=$('#timing-year');if(!year.value)year.value=new Date().getFullYear();year.min=active.profile?.date?.slice(0,4)||'1900';$('#timing-load').disabled=active.chart.status!=='calculated';setChartView(currentView)};
 createShell();window.renderTimingOverview();
})();
