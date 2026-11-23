'use strict';
let accountUser=null,codeTimer,channelState=null;
const savedReportBody=$('#saved-report-body');
if(savedReportBody&&!savedReportBody.parentElement.classList.contains('message-row')){const row=node('section',undefined,'message-row message-row-ai report-opening-row');savedReportBody.before(row);savedReportBody.classList.add('message-bubble','message-bubble-ai');row.append(savedReportBody);$('#saved-report-followups').classList.add('message-thread')}
function applyCollectionFold(box,limit=2){
 const items=[...box.children].filter(item=>!item.classList.contains('collection-fold-actions'));const old=box.querySelector(':scope > .collection-fold-actions');if(old)old.remove();
 if(items.length<=limit){items.forEach(item=>item.hidden=false);return}
 const controls=node('div',undefined,'collection-fold-actions'),expand=node('button','展开','text-button'),collapse=node('button','收起','text-button');expand.type=collapse.type='button';controls.append(expand,collapse);box.append(controls);
 const setExpanded=value=>{items.forEach((item,index)=>item.hidden=!value&&index>=limit);controls.setAttribute('aria-expanded',String(value));expand.disabled=value;collapse.disabled=!value};
 expand.onclick=()=>setExpanded(true);collapse.onclick=()=>{setExpanded(false);box.scrollIntoView({behavior:'smooth',block:'start'})};setExpanded(false);
}
function ensureLoginConsent(){
 let box=$('#login-data-consent');
 if(!box){box=document.createElement('label');box.id='login-data-consent';box.className='check';box.innerHTML='<input type="checkbox" id="login-consent"><span>我已阅读并同意《隐私政策》，同意星序为计算星盘、生成解读、保存报告及提供账号权益而处理相关资料。</span>';$('#login-submit').before(box)}
 return $('#login-consent');
}
function applyAccountConsent(){
 ['#ai-consent','#annual-consent','#experience-consent'].forEach(sel=>{const el=$(sel);if(el)el.checked=true});
 const profile=$('#birth-form input[name="consent"]');if(profile)profile.checked=true;
}
$('#redeem-code').textContent='兑换邀请码';
const inviteHint=$('#use-topic-credit').nextElementSibling;
if(inviteHint)inviteHint.textContent='套餐中的年报、单项、多维与追问权益分别计数；成功生成才扣减，失败自动恢复。邀请码仍按原商品类型兑换，不会自动续费。';
function showChannelState(){
 if(!channelState)return;
 const phoneOption=channel.querySelector('option[value="phone"]');
 const enabled=channelState.phone.configured&&channelState.phone.sdkInstalled;
 phoneOption.disabled=!enabled;phoneOption.textContent=enabled?'手机验证码':'手机验证码（审核／配置后开放）';
 if(channel.value==='phone'&&!enabled){channel.value='email';target.type='email';target.placeholder='请输入邮箱';}
 const v=channelState[channel.value];
 $('#channel-status').textContent=!v.configured?(channel.value==='email'?'邮箱发送服务尚未配置，暂不能收取验证码。':'短信尚未开通或配置，暂不能收取验证码。'):(channel.value==='phone'&&!v.sdkInstalled?'短信发送组件未安装，请联系管理员。':'发送配置已填写，请获取验证码并查收以完成测试。');
}
api('auth/channels').then(v=>{channelState=v;showChannelState()}).catch(()=>{});
const channel=$('#login-channel'),target=$('#login-target'),loginStatus=$('#login-status');
channel.onchange=()=>{target.type=channel.value==='email'?'email':'tel';target.autocomplete=channel.value==='email'?'email':'tel';target.placeholder=channel.value==='email'?'请输入邮箱':'请输入中国大陆11位手机号';target.value='';showChannelState()};
async function refreshAccount(){
 const v=await api('auth/me');accountUser=v.user;loggedIn=!!accountUser;accessReady=true;
 $('#login-panel').hidden=!!accountUser;$('#logged-panel').hidden=!accountUser;
 $('#account-state').textContent=accountUser?'已登录 · '+accountUser.identity:'登录后可在其他设备读取账号内的记录，星盘与已生成解读会自动保存，供你随时调阅。';
 $('#history').hidden=!accountUser;$('#clear').hidden=!accountUser;
 if(accountUser){await renderAccountCharts();await renderAccountReports();await renderAccountOrders();await refreshEntitlements();if(window.renderRectificationResume)await window.renderRectificationResume()}else clearPrivateView();
 if(accountUser)applyAccountConsent();else ensureLoginConsent();
}
async function renderAccountOrders(){
 let heading=$('#account-orders-title'),box=$('#account-orders');
 if(!heading){heading=node('h3','我的订单');heading.id='account-orders-title';box=node('div');box.id='account-orders';$('#logout').before(heading,box)}
 const value=await api('account/orders');box.replaceChildren();
 if(!value.items.length){box.append(node('p','暂时没有支付订单。','hint'));return}
 const names={annual:'年度报告',topic:'多维综合解读',single:'单项解读',consult:'全盘系统分析',explorer_starter:'探索体验包',explorer_deep:'深度探索包',rectification:'出生时间校准'},states={created:'待支付',pending:'待确认',paid:'已支付',closed:'已关闭',refunding:'退款处理中',refunded:'已退款',failed:'失败'};
 const channels={wechat:'微信支付',alipay:'支付宝'};
 for(const order of value.items){const card=node('article',undefined,'card');card.append(node('h3',(names[order.product]||order.product)+(order.productRef?' · '+order.productRef+'年':'')),node('p','¥'+(order.amountFen/100).toFixed(2)+' · '+(channels[order.channel]||order.channel)+' · '+(states[order.status]||order.status)+' · '+new Date(order.created*1000).toLocaleString(),'hint'));box.append(card)}applyCollectionFold(box,2);
}
async function renderAccountCharts(){
 const v=await api('account/charts');const box=$('#account-charts');box.replaceChildren();
 if(!v.items.length)box.append(node('p','账号内暂时没有星盘。','hint'));
 for(const item of v.items){const card=node('div',undefined,'card'),gender=item.profile.gender==='female'?'女':item.profile.gender==='male'?'男':'';card.append(node('h3',item.profile.profileName||item.profile.placeLabel||'我的星盘'),node('p',[item.profile.date,item.profile.time,item.profile.placeLabel,gender,'已保存'+item.reportCount+'份解读'].filter(Boolean).join(' · '),'hint'));const b=node('button','打开星盘与解读','secondary');b.onclick=()=>busy(b,async()=>{const r=await api('account/charts/'+item.id+'/open',{});localStorage.setItem('jyoti-current-session',r.session);await restoreCurrentSession();location.hash='chart';go('chart')});const remove=node('button','删除星盘','text-button danger-button');remove.onclick=()=>busy(remove,()=>deleteSavedChart(item));card.append(b,remove);box.append(card)}
}
$('#send-code').onclick=e=>busy(e.currentTarget,async()=>{
 loginStatus.textContent='正在发送…';
 try{await api('auth/code',{channel:channel.value,target:target.value});loginStatus.textContent='验证码已提交发送，请查收。';let left=60;const b=$('#send-code');clearInterval(codeTimer);codeTimer=setInterval(()=>{left--;b.disabled=left>0;b.textContent=left>0?left+'秒后重新获取':'获取验证码';if(left<=0)clearInterval(codeTimer)},1000);setTimeout(()=>{b.disabled=true;b.textContent='60秒后重新获取'},0)}catch(e){loginStatus.textContent=e.message;throw e}
});
$('#login-submit').onclick=e=>busy(e.currentTarget,async()=>{try{if(!ensureLoginConsent().checked)throw Error('请先勾选登录时的数据处理说明');await api('auth/login',{channel:channel.value,target:target.value,code:$('#login-code').value,consent:true});$('#login-code').value='';loginStatus.textContent='登录成功，数据处理同意已保存；后续服务无需重复勾选。';await refreshAccount();await restoreCurrentSession();const next=pendingService||'mine';pendingService='';location.hash=next;go(next)}catch(e){loginStatus.textContent=e.message;throw e}});
$('#claim-chart').onclick=e=>busy(e.currentTarget,async()=>{if(!session)throw Error('请先生成或打开当前星盘');await api('account/claim',{}, {'X-Jyoti-Session':session});await renderAccountCharts();loginStatus.textContent='当前星盘已保存到账号。'});
$('#logout').onclick=e=>busy(e.currentTarget,async()=>{await api('auth/logout',{});localStorage.removeItem('jyoti-current-session');location.reload()});
window.addEventListener('hashchange',()=>{if(location.hash==='#mine')refreshAccount().catch(e=>loginStatus.textContent=e.message)});
refreshAccount().then(async()=>{if(loggedIn){await restoreCurrentSession();if(pendingService){const next=pendingService;pendingService='';location.hash=next;go(next)}}}).catch(e=>loginStatus.textContent=e.message);

async function renderAccountReports(){
 const v=await api('account/reports'),box=$('#account-reports');box.replaceChildren();
 if(!v.items.length){box.append(node('p','还没有生成的解读。完成后会按类型自动保存到这里，无需手动保存。','hint'));return}
 const groups=new Map();
 for(const item of v.items){const category=reportCategory(item);if(!groups.has(category.key))groups.set(category.key,{...category,items:[]});groups.get(category.key).items.push(item)}
 const order=['natal','annual','single','topic','consult','other'];
 for(const key of order){
  const group=groups.get(key);if(!group)continue;
  const details=node('details',undefined,'report-group'),summary=node('summary'),label=node('span');
  label.append(node('b',group.title),node('small','展开查看每次独立生成的记录'));
  summary.append(label,node('em',group.items.length+' 份'));
  const records=node('div',undefined,'report-group-records');
  for(const item of group.items){
   const card=node('article',undefined,'card report-record'),title=reportTitle(item);
   const created=new Date(item.created*1000).toLocaleDateString(),updated=new Date(item.updated*1000).toLocaleDateString();
   card.append(node('h3',title),node('p','生成于 '+created+(updated!==created?' · 最近更新 '+updated:''),'hint'));
  const b=node('button','阅读已保存报告','secondary');b.onclick=()=>busy(b,async()=>{
   const report=await api('account/reports/'+encodeURIComponent(item.id));
   const natal=report.kind==='natal'||report.scope==='natal:';selectedSavedReport=report;$('#delete-saved-report').hidden=natal;$('#continue-topic-report').hidden=!(natal||report.topicRequest||report.product==='consult');$('#continue-topic-report').textContent=natal?'继续本命报告追问 ↗':report.product==='consult'?'继续本次连续咨询 ↗':'继续这份专题 · 剩余追问 ↗';
   $('#saved-report-title').textContent=reportTitle(report);$('#saved-report-meta').textContent='已保存的历史内容 · 查看不会重新调用AI';
   renderReading($('#saved-report-body'),report.text);$('#saved-report-followups').replaceChildren();
   for(const item of report.followups){const userRow=node('section',undefined,'message-row message-row-user'),userBubble=node('p',item.question,'message-bubble message-bubble-user');userRow.append(userBubble);const aiRow=node('section',undefined,'message-row message-row-ai'),body=node('article',undefined,'reading-copy message-bubble message-bubble-ai foldable-reading');aiRow.append(body);$('#saved-report-followups').append(userRow,aiRow);renderReading(body,item.answer)}
   location.hash='report-detail';go('report-detail');
   });card.append(b);if(item.kind!=='natal'&&item.scope!=='natal:'){const remove=node('button','删除这份报告','text-button danger-button');remove.onclick=()=>busy(remove,()=>deleteSavedReport(item));card.append(remove)}records.append(card);
  }
  details.append(summary,records);box.append(details);
 }
 applyCollectionFold(box,2);
}
function reportCategory(item){
 if(item.kind==='natal')return {key:'natal',title:'本命解读'};
 if(item.kind==='annual'||item.kind==='annual-basic')return {key:'annual',title:'年度与流年'};
 if(item.product==='single')return {key:'single',title:'单项解读'};
 if(item.product==='topic')return {key:'topic',title:'多盘专题'};
 if(item.product==='consult')return {key:'consult',title:'连续咨询'};
 return {key:'other',title:'其他解读'};
}
function reportTitle(item){
 if(item.kind==='natal')return '本命AI解读';
 if(item.kind==='annual-basic')return (item.scope.split(':')[1]||'')+'年 · 流年基础报告';
 if(item.kind==='annual')return (item.scope.split(':')[1]||'')+'年 · 年度AI解读';
 return ({single:'单项AI解读',topic:'多盘专题分析',consult:'连续AI咨询'})[item.product]||'已保存的AI解读';
}

let selectedSavedReport=null;
async function deleteSavedChart(item){
 if(!confirm('删除这张星盘及其全部解读报告、追问？删除后无法恢复。本机记录需另行删除。'))return;
 await api('account/charts/'+encodeURIComponent(item.id),null,{},'DELETE');
 if(active?.recordId===item.id){localStorage.removeItem('jyoti-current-session');clearPrivateView();renderLocalRecords()}
 if(selectedSavedReport?.chartId===item.id){selectedSavedReport=null;$('#saved-report-body').replaceChildren();$('#saved-report-followups').replaceChildren()}
 await renderAccountCharts();await renderAccountReports();toast('星盘及关联解读已删除');
}
async function deleteSavedReport(item){
 if(item.kind==='natal'||item.scope==='natal:')throw Error('本命报告随星盘保留，不能单独删除');
 if(!confirm('删除这份解读报告及其追问？星盘和其他报告会保留。删除后无法恢复，本机记录需另行删除。'))return;
 const result=await api('account/reports/'+encodeURIComponent(item.id),null,{},'DELETE');
 if(active?.recordId===result.chartId){
  if(result.scope==='natal:'){reading='';$('#natal-upgrade').hidden=true;$('#ai-result').replaceChildren();delete followupReadings.natal;renderFollowups('natal');$('#natal-followup').hidden=true}
  else if(/^annual:\d+$/.test(result.scope)){const year=result.scope.split(':')[1];delete annualReadings[year];delete followupReadings[result.scope];if(String($('#year').value)===year){resetAnnual();renderFollowups('annual')}}
  else if(result.scope==='annual-basic:'+$('#year').value)$('#annual-result').replaceChildren();
 }
 if(selectedSavedReport?.id===item.id){selectedSavedReport=null;$('#saved-report-body').replaceChildren();$('#saved-report-followups').replaceChildren();location.hash='mine';go('mine')}
 await renderAccountCharts();await renderAccountReports();toast('解读报告及追问已删除');
}
$('#delete-saved-report').onclick=e=>busy(e.currentTarget,async()=>{if(!selectedSavedReport)throw Error('请先打开一份报告');await deleteSavedReport(selectedSavedReport)});

async function refreshEntitlements(){
 if(!loggedIn)return;
 const result=await api('account/entitlements'),reports=await api('account/reports');
 const activeSingle=reports.items.find(x=>x.product==='single'&&x.remainingRounds>0),activeTopic=reports.items.find(x=>x.product==='topic'&&x.remainingRounds>0),activeConsult=reports.items.find(x=>x.product==='consult'&&x.remainingRounds>0);
 const balances=$$('#exploration-balance b');balances[0].textContent=result.exploration.annual;balances[1].textContent=result.exploration.single;balances[2].textContent=result.exploration.topic;balances[3].textContent=result.exploration.followup;
 const cards=$$('#exploration-balance>div'),values=[result.exploration.annual,result.exploration.single,result.exploration.topic,result.exploration.followup];
 const openPurchase=(product,tab='single')=>{location.hash='pricing';go('pricing');selectServiceTab(tab);setTimeout(()=>{const target=product==='followup'?document.querySelector('[data-service-panel="bundles"]'):document.querySelector('[data-product="'+product+'"]')?.closest('article');target?.scrollIntoView({behavior:'smooth',block:'center'})},80)};
 const enterAnnual=()=>{location.hash='reading';go('reading');setTimeout(()=>$('#annual-ai')?.scrollIntoView({behavior:'smooth',block:'center'}),80)};
 const actions=[()=>values[0]>0?enterAnnual():openPurchase('annual'),()=>values[1]>0||activeSingle?activeSingle?resumeActiveService('single'):openEntitledService('single'):openPurchase('single'),()=>values[2]>0||activeTopic?activeTopic?resumeActiveService('topic'):openEntitledService('topic'):openPurchase('topic'),()=>values[3]>0?resumeNatalFollowup():openPurchase('followup','bundles')];
 cards.forEach((card,index)=>{card.classList.add('entitlement-entry');card.tabIndex=0;card.setAttribute('role','button');card.setAttribute('aria-label',card.querySelector('span').textContent+'，剩余'+values[index]+'次，'+(values[index]>0?'点击使用':'点击获取'));card.querySelector('small').textContent=values[index]>0?'点击使用 ↗':'点击获取 ↗';card.onclick=async()=>{try{await actions[index]()}catch(error){toast(error.message)}};card.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();card.click()}}});
 $('#quota-status').textContent='免费本命待生成 '+result.remaining.natal+' 张 · 全盘系统分析 '+(result.remaining.consult||0)+' 次';
 renderEntitlementHistory(result.history||[]);
 $('#use-topic-credit').textContent=activeTopic?'继续未完成专题 · 剩余 '+activeTopic.remainingRounds+' 轮 ↗':'使用专题权益 · 自选2–5张图谱 ↗';$('#use-topic-credit').hidden=result.remaining.topic<1&&!activeTopic;
 const panel=$('#quota-status').parentElement;
 const ensureAction=(id,label,cls,handler)=>{let b=$('#'+id);if(!b){b=node('button',label,cls);b.id=id;panel.append(b)}b.textContent=label;b.hidden=false;b.disabled=false;b.onclick=()=>busy(b,handler);return b};
 const single=ensureAction('use-single-credit',activeSingle?'继续单项解读 · 剩余 '+activeSingle.remainingRounds+' 轮 ↗':'使用单项解读权益 · 选择1张图谱 ↗','secondary',()=>activeSingle?resumeActiveService('single'):openEntitledService('single'));
 single.hidden=(result.remaining.single||0)<1&&!activeSingle;
 const consult=ensureAction('use-consult-credit',activeConsult?'继续连续咨询 · 剩余 '+activeConsult.remainingRounds+' 轮 ↗':'使用连续咨询权益 · 选择分盘后开始30轮 ↗','primary',()=>activeConsult?resumeActiveService('consult'):openEntitledService('consult'));
 consult.hidden=result.remaining.consult<1&&!activeConsult;
 const annual=ensureAction('use-annual-credit','使用年度权益 · 生成本年度解读 ↗','secondary',async()=>{location.hash='reading';go('reading');await openAnnualOffer()});
 annual.hidden=(result.remaining['annual:any']||0)<1;
 const followup=ensureAction('use-natal-followup','使用追问权益 · 打开本命报告 ↗','secondary',()=>resumeNatalFollowup());
 followup.hidden=(result.remaining.followup||0)<1;
 result.remaining.activeSingleRounds=activeSingle?.remainingRounds||0;result.remaining.activeTopicRounds=activeTopic?.remainingRounds||0;result.remaining.activeConsultRounds=activeConsult?.remainingRounds||0;return result.remaining;
}
function $$(selector){return [...document.querySelectorAll(selector)]}
function renderEntitlementHistory(items){
 const box=$('#entitlement-history');box.replaceChildren();
 if(!items.length){box.append(node('p','暂无使用记录。购买套餐并使用权益后，会在这里关联订单与解读记录。','hint'));return}
 const names={'annual:any':'年度报告',single:'单项解读',topic:'多维综合解读',consult:'全盘系统分析',followup:'追问次数',natal:'本命报告'},states={consumed:'已使用',reserved:'生成中',released:'已恢复'};
 for(const item of items){const row=node('article',undefined,'entitlement-history-row'),top=node('div');top.append(node('b',names[item.product]||(/^annual:/.test(item.product)?'年度报告':item.product)),node('span',states[item.state]||item.state));row.append(top,node('small',new Date(item.created*1000).toLocaleString()+(item.sourceOrderId?' · 来源订单 '+item.sourceOrderId.slice(0,10):'')+(item.reportRef?' · 已关联报告':'')));box.append(row)}
}
async function openEntitledService(plan){
 if(!loggedIn){pendingService='pricing';location.hash='mine';go('mine');toast('请先登录后使用已兑换权益');return false}
 if(!session){
  const charts=await api('account/charts');
  if(!charts.items.length){toast('权益已保存在账号；请先创建一张星盘，之后可直接进入服务');location.hash='profile';go('profile');return false}
  const opened=await api('account/charts/'+encodeURIComponent(charts.items[0].id)+'/open',{});
  localStorage.setItem('jyoti-current-session',opened.session);await restoreCurrentSession();
 }
 openExperience(plan);return true;
}
async function resumeActiveService(plan){
 if(!loggedIn||!['single','topic','consult'].includes(plan))return false;
 const list=await api('account/reports');
 const item=list.items.find(x=>x.product===plan&&x.remainingRounds>0);
 if(!item)return false;
 const report=await api('account/reports/'+encodeURIComponent(item.id));selectedSavedReport=report;
 const opened=await api('account/charts/'+encodeURIComponent(report.chartId)+'/open',{});
 localStorage.setItem('jyoti-current-session',opened.session);await restoreCurrentSession();openExperience(plan);
 if(plan==='consult')restoreConsultReport(report);else restoreTopicReport(report);
 toast('已直接恢复未完成的'+(plan==='consult'?'连续咨询':plan==='single'?'单项解读':'多盘专题')+'，剩余 '+item.remainingRounds+' 轮');return true;
}
async function resumeNatalFollowup(report=null){
 if(!loggedIn)throw Error('请先登录后使用追问权益');
 if(!report){const list=await api('account/reports');const item=list.items.find(x=>x.kind==='natal'||x.scope==='natal:');if(!item){toast('请先创建星盘并生成本命报告');location.hash='profile';go('profile');return false}report=await api('account/reports/'+encodeURIComponent(item.id))}
 const opened=await api('account/charts/'+encodeURIComponent(report.chartId)+'/open',{});localStorage.setItem('jyoti-current-session',opened.session);await restoreCurrentSession();location.hash='reading';go('reading');setTimeout(()=>$('#natal-followup')?.scrollIntoView({behavior:'smooth',block:'start'}),100);return true;
}
$('#redeem-code').onclick=e=>busy(e.currentTarget,async()=>{
 if(!loggedIn)throw Error('请先登录后兑换');
 const code=$('#experience-code').value.trim();if(!code)throw Error('请输入体验码');
 try{const result=await api('account/redeem',{code});$('#experience-code').value='';const names={single:'¥4.9单项解读1份＋2轮追问',topic:'¥19.9多维综合解读1份＋5轮追问',consult:'¥29.9全盘系统分析＋30轮连续咨询',rectification:'¥39.9出生时间校准1次','annual:any':'¥1年度报告1份'};$('#redeem-status').textContent=result.alreadyRedeemed?'这枚邀请码已在你的账号兑换，无需重复兑换。':'兑换成功：'+(names[result.product]||'对应服务权益')+'，权益已保存到账号；有效期与使用规则以后台配置为准。';await refreshEntitlements();if(result.product==='rectification'){await window.rectificationReady;await window.openRectificationProduct()}else if(!result.alreadyRedeemed){if(result.product==='single')await openEntitledService('single');else if(result.product==='topic')await openEntitledService('topic');else if(result.product==='consult')await openEntitledService('consult');else if(result.product==='annual:any')await openAnnualOffer()}}
 catch(e){$('#redeem-status').textContent=e.message;throw e}
});
$('#use-topic-credit').onclick=async()=>{try{if(!await resumeActiveService('topic'))await openEntitledService('topic')}catch(e){toast(e.message)}};
$('#continue-topic-report').onclick=e=>busy(e.currentTarget,async()=>{
 const report=selectedSavedReport;if(report?.kind==='natal'||report?.scope==='natal:')return resumeNatalFollowup(report);if(!report?.topicRequest&&report?.product!=='consult')throw Error('此报告没有可恢复的咨询上下文');
 const opened=await api('account/charts/'+encodeURIComponent(report.chartId)+'/open',{});
 localStorage.setItem('jyoti-current-session',opened.session);await restoreCurrentSession();
 if(report.product==='consult'){openExperience('consult');restoreConsultReport(report)}else{openExperience('topic');restoreTopicReport(report)}
});
