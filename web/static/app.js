'use strict';
const $=s=>document.querySelector(s), KEY='jyoti-web-history-v1';
let accessReady=false,loggedIn=false,pendingService='';
let active=null,session='',reading='',annualReadings={},followupReadings={},mode='d1',toastTimer;
const signs=['白羊','金牛','双子','巨蟹','狮子','处女','天秤','天蝎','射手','摩羯','水瓶','双鱼'];
const cellPos=[[1,2],[1,3],[1,4],[2,4],[3,4],[4,4],[4,3],[4,2],[4,1],[3,1],[2,1],[1,1]];
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n}
function requireAccountView(destination='reading'){if(loggedIn)return true;pendingService=destination;location.hash='mine';go('mine');toast('请先登录，星盘和解读会自动保存到账号');return false}
function toast(t){$('#toast').textContent=t;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,5500)}
function go(name){if(['profile','chart','payment','experience','report-detail'].includes(name)&&!loggedIn){pendingService=name;name='mine';if(location.hash!=='#mine')location.hash='mine'}if(!document.getElementById(name))name='home';document.querySelectorAll('.screen').forEach(x=>x.hidden=x.id!==name);document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('active',x.dataset.go===name));if(name==='mine')renderLocalRecords();window.scrollTo(0,0)}
window.addEventListener('hashchange',()=>go(location.hash.slice(1)));document.addEventListener('click',e=>{const b=e.target.closest('[data-go]');if(b){location.hash=b.dataset.go;go(b.dataset.go)}});
async function api(path,body,headers={},method){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),175000);try{const r=await fetch('/api/'+path,{method:method||(body?'POST':'GET'),headers:{'Content-Type':'application/json',...headers},body:body?JSON.stringify(body):undefined,signal:controller.signal});const raw=await r.text();let v={};try{v=raw?JSON.parse(raw):{}}catch{v={detail:r.ok?'服务返回格式异常':'服务器暂时未完成请求，请稍后重试'}}if(r.status===401&&!path.startsWith('auth/')){loggedIn=false;clearPrivateView();pendingService=location.hash.slice(1);location.hash='mine';go('mine')}if(!r.ok)throw Error(typeof v.detail==='string'?v.detail:'请检查填写内容后再试');return v}catch(e){if(e.name==='AbortError')throw Error('请求超时，请稍后再试');if(e instanceof TypeError)throw Error('无法连接服务，请检查网络');throw e}finally{clearTimeout(timer)}}
async function busy(b,fn){const text=b.textContent;b.disabled=true;b.textContent='正在处理…';try{await fn()}catch(e){toast(e.message)}finally{b.disabled=false;b.textContent=text}}
const form=$('#birth-form');const identityFields=document.createElement('div');identityFields.className='two';identityFields.innerHTML='<label>星盘昵称 / 名字<input required name="profileName" maxlength="40" placeholder="例如：我的星盘、家人名字" autocomplete="off"></label><label>性别<select required name="gender"><option value="">请选择</option><option value="female">女</option><option value="male">男</option></select></label>';form.prepend(identityFields);form.elements.date.max=new Date().toLocaleDateString('en-CA');
form.elements.placeLabel.addEventListener('input',()=>{form.elements.latitude.value='';form.elements.longitude.value='';$('#map-status').textContent='地点已更改，请重新匹配或手动填写坐标。'});
$('#match').onclick=e=>busy(e.currentTarget,async()=>{if(!requireAccountView('profile'))return;if(!form.elements.consent.checked)throw Error('请先阅读并勾选资料使用说明');const v=await api('place',{address:form.elements.placeLabel.value});for(const k of ['latitude','longitude','timezone'])form.elements[k].value=v[k];$('#map-status').textContent=`已匹配：${v.placeLabel} · ${v.latitude}, ${v.longitude}（WGS84）`});
form.addEventListener('invalid',()=>{form.querySelector('details').open=true},true);
form.onsubmit=e=>{e.preventDefault();busy(form.querySelector('[type=submit]'),async()=>{if(!requireAccountView('profile'))return;const p=Object.fromEntries(new FormData(form));p.profileName=p.profileName.trim();if(!p.profileName)throw Error('请填写星盘昵称或名字');p.latitude=Number(p.latitude);p.longitude=Number(p.longitude);p.accuracy=Number(p.accuracy);p.fold=p.fold===''?null:Number(p.fold);p.consent=form.elements.consent.checked;const v=await api('chart',p);active={profile:p,chart:v.chart,recordId:v.recordId};session=v.session;localStorage.setItem('jyoti-current-session',session);reading='';$('#natal-upgrade').hidden=true;annualReadings={};followupReadings={};renderFollowups('natal');$('#natal-followup').hidden=true;resetAnnual();$('#annual-result').replaceChildren();$('#ai-result').textContent='';render();location.hash='chart';go('chart')})};
function render(){
 if(!active)return;
 $('#chart-empty').hidden=true;$('#chart-content').hidden=false;
 $('#chart-label').textContent=`${active.profile.profileName||'我的星盘'} · ${active.profile.date} · ${active.profile.time} · ${active.profile.placeLabel}`;
 const c=active.chart,div=c.divisions?.[mode],base=mode==='d1';
 const ps=base?c.planets:(div?.planets||[]),asc=base?c.ascendant:div?.ascendant;
 const title=base?'D1 · 本命盘':div?.title||mode.toUpperCase();
 $('#varga-select').value=mode;
 const choice=document.querySelector('[data-varga="'+mode+'"]');
 if(choice)$('#varga-current').textContent=choice.querySelector('b').textContent;
 document.querySelectorAll('[data-varga]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.varga===mode)));
 $('#varga-guide').replaceChildren(node('h2',base?'本命位置':div?.theme||'请重新生成星盘'),node('p',base?'D1为实际天体黄经与本命整宫位置，是辅助分盘的共同计算来源。':div?.note||(c.status!=='calculated'?'估计时刻不提供辅助分盘；请用准确时刻重新计算。':'此记录生成于旧版本，不含新增分盘数据。请在“我的空间”选择重新计算。'),'hint'));
 $('#chart-note').textContent=base?(c.message||'Lahiri 恒星黄道 · Whole sign 整宫制 · WGS84'):'Parashari 分盘星座映射 · 不代表实测天空位置或精确分盘度数。高阶分盘对出生时刻敏感。';
 const grid=$('#diagram');grid.replaceChildren();grid.hidden=!ps.length;
 if(ps.length){signs.forEach((s,i)=>{const n=node('div',s,'cell');n.style.gridArea=`${cellPos[i][0]}/${cellPos[i][1]}`;if(asc?.signIndex===i)n.append(node('b','↑ 上升'));ps.filter(p=>p.signIndex===i).forEach(p=>n.append(node('b',p.name)));grid.append(n)});const center=node('div',undefined,'center');center.append(node('strong','✧'),node('span',mode.toUpperCase()),node('span',asc?'上升 · '+asc.sign:'上升不可用'));grid.append(center)}
 $('#positions-title').textContent=title+' · '+(base?'天体位置':'映射位置');
 $('#planet-list').replaceChildren(...ps.map(p=>{const r=node('div',undefined,'row');r.append(node('span',p.name+(base&&p.retrograde?' ℞':'')),node('span',`${p.sign}${base?' '+p.degree.toFixed(2)+'°':''}${p.house?' · 第'+p.house+'宫':''}`));return r}));
 $('#planet-list').hidden=!ps.length;
 renderPeriods(c);renderReading($('#ai-result'),reading);$('#natal-followup').hidden=!reading;renderFollowups('natal');if(reading)refreshNatalFollowupAccess().catch(e=>toast(e.message));if(window.renderTimingOverview)window.renderTimingOverview();
}
document.querySelectorAll('[data-varga]').forEach(b=>b.onclick=()=>{mode=b.dataset.varga;render();$('#varga-picker').open=false});
$('#varga-select').onchange=e=>{mode=e.target.value;render()};
$('#period-date').value=new Date().toISOString().slice(0,10);
$('#period-date').onchange=()=>{if(active)renderPeriods(active.chart)};
$('#annual').onclick=()=>openAnnualOffer();
// Build a small Markdown subset with DOM nodes only; provider text never becomes HTML.
function inlineText(parent,text){const parts=text.split(/(\*\*[^*]+\*\*)/g);parts.forEach(p=>{if(p.startsWith('**')&&p.endsWith('**'))parent.append(node('strong',p.slice(2,-2)));else parent.append(document.createTextNode(p))})}
function markdownTableCells(line){let value=line.trim();if(!value.includes('|'))return null;if(value.startsWith('|'))value=value.slice(1);if(value.endsWith('|'))value=value.slice(0,-1);const cells=value.split('|').map(cell=>cell.trim());return cells.length>=2&&cells.some(Boolean)?cells:null}
function markdownTableAt(lines,start){const header=markdownTableCells(lines[start]||''),separator=markdownTableCells(lines[start+1]||'');if(!header||!separator||separator.length!==header.length||!separator.every(cell=>/^:?-{3,}:?$/.test(cell)))return null;const rows=[];let next=start+2;while(next<lines.length&&lines[next].trim()){const cells=markdownTableCells(lines[next]);if(!cells||cells.length!==header.length||cells.every(cell=>/^:?-{3,}:?$/.test(cell)))break;rows.push(cells);next++}const wrapper=node('div',undefined,'reading-table-scroll'),table=node('table',undefined,'reading-table'),thead=node('thead'),headRow=node('tr'),tbody=node('tbody');for(const cell of header){const th=node('th');th.scope='col';inlineText(th,cell);headRow.append(th)}thead.append(headRow);for(const row of rows){const tr=node('tr');for(const cell of row){const td=node('td');inlineText(td,cell);tr.append(td)}tbody.append(tr)}table.append(thead,tbody);wrapper.append(table);return {element:wrapper,next}}
let reportFoldSequence=0;
function ensureReportFoldControls(box){
 const hasContent=Boolean((box.textContent||'').trim());let controls=box.nextElementSibling;
 if(!controls?.classList.contains('report-fold-actions')){controls=node('div',undefined,'report-fold-actions');controls.dataset.foldTarget=box.id||(box.id='foldable-report-'+(++reportFoldSequence));const expand=node('button','展开','text-button'),collapse=node('button','收起','text-button');expand.type=collapse.type='button';expand.dataset.action='expand';collapse.dataset.action='collapse';controls.append(expand,collapse);box.after(controls)}
 controls.hidden=!hasContent;if(!hasContent){box.classList.remove('report-is-collapsed');return}
 const expand=controls.querySelector('[data-action="expand"]'),collapse=controls.querySelector('[data-action="collapse"]');
 const setExpanded=value=>{box.classList.toggle('report-is-collapsed',!value);box.setAttribute('aria-expanded',String(value));expand.disabled=value;collapse.disabled=!value;if(value)box.style.removeProperty('max-height')};
 expand.onclick=()=>setExpanded(true);collapse.onclick=()=>{setExpanded(false);box.scrollIntoView({behavior:'smooth',block:'start'})};setExpanded(!box.classList.contains('report-is-collapsed'));
}
function renderReading(box,text){box.replaceChildren();let list=null;const lines=(text||'').split('\n');for(let index=0;index<lines.length;){const t=lines[index].trim();if(!t){list=null;index++;continue}const markdownTable=markdownTableAt(lines,index);if(markdownTable){list=null;box.append(markdownTable.element);index=markdownTable.next;continue}let n;if(/^#{1,3}\s/.test(t)){n=node('h3');inlineText(n,t.replace(/^#{1,3}\s+/,''));list=null}else if(/^[-*]\s/.test(t)){if(!list){list=node('ul');box.append(list)}n=node('li');inlineText(n,t.slice(2));list.append(n);index++;continue}else{n=node('p');inlineText(n,t);list=null}box.append(n);index++}if(['ai-result','annual-ai-result','topic-real-report','saved-report-body'].includes(box.id)||box.classList.contains('foldable-reading'))ensureReportFoldControls(box)}
let planSequence=0,planTimer,planDraftTimer,lastPlannedDraft='',planDraftRequests=0,natalPlanSession='',plannedChapters=new Set();
function reportContext(kind){
 const box=$(kind==='topic'?'#topic-real-report':kind==='consult'?'#consult-messages':'#ai-result'),headings=[...(box?.querySelectorAll('h3')||[])];
 if(!box)return {title:'报告重点',text:''};
 let heading=headings[0]||null,best=-Infinity;
 for(const item of headings){const top=item.getBoundingClientRect().top;if(top<=innerHeight*.58&&top>best){heading=item;best=top}}
 if(!heading)return {title:'报告重点',text:(box.textContent||'').slice(0,900)};
 let text='',cursor=heading.nextElementSibling;
 while(cursor&&!/^H[1-3]$/.test(cursor.tagName)&&text.length<1000){text+=' '+cursor.textContent;cursor=cursor.nextElementSibling}
 return {title:heading.textContent.trim()||'报告重点',text:text.trim().slice(0,1000)};
}
function planElements(kind){const key=kind==='consult'?'topic':kind;return {questions:$('#'+key+'-plan-questions'),status:$('#'+key+'-plan-status'),context:$('#'+key+'-plan-context'),direction:$('#'+key+'-plan-direction'),input:$(kind==='topic'||kind==='consult'?'#consult-question':'#natal-question'),refined:$('#'+key+'-refined')}}
function renderFollowupPlan(kind,result){
 const el=planElements(kind);if(!el.questions)return;el.questions.replaceChildren();
 for(const item of result.questions||[]){const button=node('button',undefined,'followup-plan-question');button.type='button';button.append(node('span',item.label,'plan-layer'),node('span',item.question,'plan-copy'));button.onclick=()=>{el.input.value=item.question;el.input.focus();el.refined.hidden=true};el.questions.append(button)}
 el.status.textContent=`推荐本身不计次 · 本次还可追问 ${result.rounds.remaining} / ${result.rounds.limit} 轮`;
 el.context.textContent=`当前结合：${result.context.chapter} · ${result.context.direction}`;
 const refined=(result.refinedQuestion||'').trim();el.refined.replaceChildren();el.refined.hidden=!refined;
 if(refined){el.refined.append(node('small','把你的想法具体成：'),node('p',refined));const use=node('button','使用这个问题','text-button');use.type='button';use.onclick=()=>{el.input.value=refined;el.refined.hidden=true;el.input.focus()};el.refined.append(use)}
}
async function loadFollowupPlan(kind,withDraft=false){
 if(!session||!reading&&kind==='natal'||kind==='topic'&&(!window.currentTopicRequest||!window.currentTopicRequest.topicQuestion)||kind==='consult'&&!experienceReportReady)return;
 const el=planElements(kind),consent=$(kind==='topic'||kind==='consult'?'#experience-consent':'#ai-consent');if(!consent?.checked){el.status.textContent='勾选上方 AI 数据处理说明后，可生成个性化追问推荐。';return}const context=reportContext(kind),sequence=++planSequence;el.status.textContent='正在结合报告与当前章节整理下一问…';
 const body={session,kind,chapterTitle:context.title,chapterText:context.text,direction:el.direction.value,draftQuestion:withDraft?el.input.value.trim():'',consent:true};
 if(kind==='topic')Object.assign(body,{topicQuestion:window.currentTopicRequest.topicQuestion,selectedCharts:window.currentTopicRequest.selectedCharts,year:window.currentTopicRequest.year,topicBaseScope:window.currentTopicRequest.topicBaseScope});
 if(kind==='consult')Object.assign(body,{selectedCharts:[...(window.consultSelectedCharts?.()||[])],year:Number($('#year').value)});
 try{const result=await api('followup/plan',body);if(sequence!==planSequence)return;renderFollowupPlan(kind,result)}catch(e){if(sequence!==planSequence)return;el.status.textContent=e.message}
}
function queueDraftRefinement(kind){clearTimeout(planDraftTimer);const value=planElements(kind).input.value.trim();if(value.length<2||value.length>80||value===lastPlannedDraft||planDraftRequests>=3)return;planDraftTimer=setTimeout(()=>{lastPlannedDraft=value;planDraftRequests++;loadFollowupPlan(kind,true)},900)}
function activateNatalPlanner(){
 const box=$('#natal-plan-questions');if(!box)return;if(natalPlanSession!==session){box.replaceChildren();$('#natal-refined').hidden=true;plannedChapters.clear();lastPlannedDraft='';planDraftRequests=0;natalPlanSession=session}if(box.childElementCount)return;loadFollowupPlan('natal');
}
$('#natal-plan-refresh').onclick=()=>loadFollowupPlan('natal',Boolean($('#natal-question').value.trim()));
$('#natal-plan-direction').onchange=()=>loadFollowupPlan('natal',Boolean($('#natal-question').value.trim()));
$('#natal-question').addEventListener('input',()=>queueDraftRefinement('natal'));
$('#ai-consent').addEventListener('change',e=>{if(e.target.checked&&reading)refreshNatalFollowupAccess()});
window.addEventListener('scroll',()=>{clearTimeout(planTimer);if($('#reading').hidden||$('#natal-followup').hidden||$('#natal-followup .followup-planner').hidden)return;planTimer=setTimeout(()=>{const chapter=reportContext('natal').title;if(plannedChapters.has(chapter))return;plannedChapters.add(chapter);loadFollowupPlan('natal',false)},1000)},{passive:true});
function resetAnnual(){const text=annualReadings[$('#year').value]||'';renderReading($('#annual-ai-result'),text);$('#annual-followup').hidden=true;renderFollowups('annual');$('#annual-ai-status').textContent=text?'年度解读已完成 · AI 生成':''}
$('#year').oninput=()=>{$('#annual-result').replaceChildren();resetAnnual()};
async function requestReading(body){let v=await api('interpret/start',body);const waitMs=body.kind==='natal'&&body.round===1?98000:180000,until=Date.now()+waitMs,jobId=v.jobId;while(v.state==='pending'&&Date.now()<until){await new Promise(resolve=>setTimeout(resolve,1800));v=await api('interpret/result?jobId='+encodeURIComponent(jobId),null,{'X-Jyoti-Session':body.session})}if(v.state!=='completed')throw Error(v.detail||'解读尚未完成，请稍后点击原按钮查看进度');return v}
function followupScope(kind,year=Number($('#year').value)){return kind==='natal'?'natal':'annual:'+year}
async function refreshNatalFollowupAccess(){
 const parent=$('#natal-followup');if(!parent||!reading||!loggedIn)return 0;let lock=$('#natal-followup-lock');
 if(!lock){lock=node('section',undefined,'natal-followup-lock');lock.id='natal-followup-lock';lock.append(node('span','探索权益','badge'),node('h3','本命报告不含免费追问'),node('p','探索体验包包含3次独立追问权益，成功回答后才扣减。'));const button=node('button','查看 ¥9.9 探索体验包 ↗','secondary');button.type='button';button.dataset.go='pricing';button.dataset.serviceTab='bundles';lock.append(button);parent.querySelector('.followup-planner').before(lock)}
 const result=await api('account/entitlements'),remaining=result.remaining.followup||0,enabled=remaining>0,planner=parent.querySelector('.followup-planner'),questionLabel=$('#natal-question').closest('label'),send=parent.querySelector('[data-followup="natal"]');
 lock.hidden=enabled;planner.hidden=!enabled;questionLabel.hidden=!enabled;send.hidden=!enabled;if(enabled){send.textContent='发送追问 · 剩余 '+remaining+' 次 ✧';activateNatalPlanner()}return remaining;
}
function renderFollowups(kind){const box=$('#'+kind+'-followup-result');if(!box)return;box.replaceChildren();const status=$('#'+kind+'-followup-status');if(status)status.textContent='';const items=followupReadings[followupScope(kind)]||[];for(const item of items){const section=node('section',undefined,'followup-answer');section.append(node('h3','你的追问'),node('p',item.question));const answer=node('article',undefined,'reading-copy foldable-reading');section.append(answer);box.append(section);renderReading(answer,item.text)}}

async function generateReading(kind){if(!requireAccountView())return;if(!session)throw Error('请先生成星盘；历史收藏需重新计算后生成新解读');const natal=kind==='natal',consent=$(natal?'#ai-consent':'#annual-consent'),status=$(natal?'#ai-status':'#annual-ai-status'),year=Number($('#year').value);if(!consent.checked)throw Error('请先同意 AI 数据处理说明');if(!natal&&(!Number.isInteger(year)||year<1900||year>2100))throw Error('请选择1900—2100之间的年份');status.textContent=natal?'正在核对D1、核心分盘与当前大小运，通常需要1–2分钟，请保持页面打开。':'正在交叉核对大小运、年度返照与年度趋势，通常需要1—2分钟，请保持页面打开。';try{const v=await requestReading({session,kind,year:natal?null:year,round:1,consent:true});if(natal){reading=v.text;renderReading($('#ai-result'),reading);$('#natal-followup').hidden=false;$('#natal-upgrade').hidden=false;await refreshNatalFollowupAccess()}else{annualReadings[year]=v.text;if(Number($('#year').value)===year)resetAnnual()}status.textContent=natal?'本命深度分析已完成 · AI生成':'首轮解读已完成 · AI 生成；可到星盘页保存。'}catch(e){status.textContent=e.message;throw e}}
$('#interpret').onclick=e=>busy(e.currentTarget,()=>generateReading('natal'));
$('#annual-ai').onclick=()=>{const text=annualReadings[$('#year').value];if(text){resetAnnual();toast('已显示历史年度报告，未重新生成')}else openAnnualOffer()};
document.querySelectorAll('[data-followup]').forEach(b=>b.onclick=()=>busy(b,async()=>{if(!requireAccountView())return;if(!session)throw Error('请重新计算星盘并完成首轮解读后继续');const kind=b.dataset.followup;if(kind==='annual'){openAnnualOffer();return}const consent=$(kind==='natal'?'#ai-consent':'#annual-consent');if(!consent.checked)throw Error('请先同意 AI 数据处理说明');const question=$('#'+kind+'-question').value.trim();if(!question)throw Error('请先填写想深入讨论的问题');const year=Number($('#year').value),scope=followupScope(kind,year),token=session,status=$('#'+kind+'-followup-status');status.textContent='正在结合首轮分析回答你的追问，请保持页面打开。';try{const v=await requestReading({session:token,kind,year:kind==='annual'?year:null,round:2,question,consent:true});if(session!==token)return;const items=followupReadings[scope]||[];followupReadings[scope]=[...items.filter(x=>x.question!==question),{question,text:v.text}];if(kind==='natal'||Number($('#year').value)===year){renderFollowups(kind);const remaining=kind==='natal'?await refreshNatalFollowupAccess():0;status.textContent=kind==='natal'?'追问已完成 · 已扣减1次权益，剩余 '+remaining+' 次。':'追问已完成。'}}catch(e){status.textContent=e.message;throw e}}));

function stored(){const v=JSON.parse(localStorage.getItem(KEY)||'[]');return Array.isArray(v)?v.filter(x=>x?.profile&&x?.chart?.planets).slice(0,20):[]}
$('#save').onclick=()=>{if(!active)return;try{const items=stored(),id=JSON.stringify(active.profile);const v={...active,reading,annualReadings,followupReadings,id,savedAt:new Date().toISOString()};localStorage.setItem(KEY,JSON.stringify([v,...items.filter(x=>x.id!==id)].slice(0,20)));toast('已保存星盘与当前 AI 解读到本机')}catch{toast('保存失败，请检查浏览器存储空间')}};
function renderLocalRecords(){const box=$('#history');try{const items=stored();box.replaceChildren();if(!items.length)box.append(node('p','还没有本机记录。生成星盘后，点击保存即可。','hint'));items.forEach(v=>{const c=node('div',undefined,'card saved');c.append(node('h2',v.profile.profileName||v.profile.placeLabel||'我的星盘'),node('small',v.profile.date+' · '+v.profile.time+' · '+v.profile.placeLabel));const open=node('button','打开记录','text-button');open.onclick=()=>{active=v;reading=v.reading||'';annualReadings=v.annualReadings||{};followupReadings=v.followupReadings||{};resetAnnual();session='';$('#annual-result').replaceChildren();render();location.hash='chart';go('chart')};const remove=node('button','删除','text-button');remove.onclick=()=>{if(confirm('删除这条本机记录？')){try{localStorage.setItem(KEY,JSON.stringify(stored().filter(x=>x.id!==v.id)));renderLocalRecords()}catch{toast('删除失败')}}};const edit=node('button','重新计算','text-button');edit.onclick=()=>{Object.entries(v.profile).forEach(([k,val])=>{if(form.elements[k]&&k!=='consent')form.elements[k].value=val??''});form.elements.consent.checked=false;location.hash='profile';go('profile')};c.append(open,edit,remove);box.append(c)})}catch{box.replaceChildren(node('p','无法读取本机记录，可尝试清空后重新保存。','hint'))}}
$('#clear').onclick=()=>{if(confirm('清空此浏览器中的所有星序记录？')){try{localStorage.removeItem(KEY);renderLocalRecords();toast('已清空')}catch{toast('清空失败')}}};
$('#year').value=new Date().getFullYear();go(location.hash.slice(1)||'home');api('status').then(s=>{if(!s.map)$('#map-status').textContent='地图服务尚未配置，可手动填写 WGS84 坐标与时区。';if(!s.ai)$('#ai-status').textContent='AI 服务尚未配置，请联系管理员。'}).catch(()=>toast('服务暂未连接，请稍后重试'));

async function restoreCurrentSession(){
 if(!loggedIn)return;
 const token=localStorage.getItem('jyoti-current-session');if(!token)return;
 try{
  const v=await api('session',null,{'X-Jyoti-Session':token});
  active={profile:v.profile,chart:v.chart,recordId:v.recordId};session=token;reading=v.reports['natal:']||'';annualReadings={};followupReadings={};
  for(const [key,text] of Object.entries(v.reports))if(/^annual:\d+$/.test(key))annualReadings[key.split(':')[1]]=text;
  for(const [key,items] of Object.entries(v.followups))followupReadings[key==='natal:'?'natal':key]=items.map(x=>({question:x.question,text:x.answer}));
  $('#natal-upgrade').hidden=!reading;render();resetAnnual();toast('已恢复当前星盘和已保存的解读');
 }catch(e){toast('暂未恢复当前星盘：'+e.message)}
}
// Restore only after account verification.

function clearPrivateView(){
 active=null;session='';reading='';annualReadings={};followupReadings={};$('#natal-upgrade').hidden=true;
 $('#chart-content').hidden=true;$('#chart-empty').hidden=false;
 for(const id of ['annual-result','ai-result','annual-ai-result','natal-followup-result','annual-followup-result','account-charts','account-reports','account-orders','entitlement-history','saved-report-body','saved-report-followups','history']){const el=document.getElementById(id);if(el)el.replaceChildren()}
 document.querySelectorAll('.report-fold-actions,.collection-fold-actions').forEach(el=>el.remove());document.querySelectorAll('.report-is-collapsed').forEach(el=>el.classList.remove('report-is-collapsed'));
 $('#natal-followup').hidden=true;$('#annual-followup').hidden=true;
}
