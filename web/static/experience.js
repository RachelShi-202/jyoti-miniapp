'use strict';
const experiencePlans={single:{title:'一个问题，先看清楚。',intro:'选1张指定盘，写下你的问题。简洁解读之后，继续2次追问。',limit:2},topic:{title:'把复杂的问题，放在一起看。',intro:'先写问题，再选择2–5张图谱。让不同视角共同回答你。',limit:5},consult:{title:'你的AI个人咨询空间',intro:'由你选择本轮重点分盘，微运与年运盘固定启用。30轮连续AI咨询，从最关心的问题开始。',limit:30}};
const chartChoices=[['d1','本命盘','整体格局'],['d2','D2','财富资源'],['d3','D3','手足行动'],['d4','D4','居所房产'],['d7','D7','养育延续'],['d9','D9','关系承诺'],['d10','D10','事业责任'],['d12','D12','父母家庭'],['d16','D16','出行享受'],['d20','D20','信念修习'],['d24','D24','学习学识'],['d27','D27','优势短板'],['d30','D30','压力应对'],['d40','D40','母系传承'],['d45','D45','父系传承'],['d60','D60','深层禀赋']];
let experiencePlan='topic',experienceRounds=0,chosenCharts=new Set(['d1','d10','d2']),experienceReportReady=false;
const continueAfterReport=node('button','继续追问 ↗','primary report-continue-button');continueAfterReport.id='continue-after-report';continueAfterReport.type='button';continueAfterReport.hidden=true;$('#experience-chat').before(continueAfterReport);
const followupChartChoice=node('section',undefined,'followup-chart-choice');followupChartChoice.id='followup-chart-choice';followupChartChoice.hidden=true;
followupChartChoice.innerHTML='<h3>这轮是否需要调整分析方向？</h3><p id="followup-chart-summary" class="hint"></p><div class="followup-chart-actions"><button id="followup-keep-charts" type="button" class="secondary">沿用当前分盘继续</button><button id="followup-change-charts" type="button" class="text-button">更换方向与分盘</button></div><div id="followup-chart-panel" hidden><span class="badge">先选择分盘</span><h3>选择本轮重点图谱</h3><p id="followup-chart-help" class="hint">请选择2–5张图谱。确认后才进入问题描述；本轮将生成约500字的追问回答，不会重复生成首份长报告。</p><div id="followup-locked-timing" class="research-chart-choice locked-chart-choice" hidden><input type="checkbox" checked disabled><span><b>微运＋年运盘</b><small>固定启用 · 不占选择数量</small></span></div><div id="followup-charts" class="research-charts"></div><p id="followup-chart-count" class="hint"></p><button id="followup-confirm-charts" type="button" class="primary">确认分盘，进入提问 ↗</button></div>';
$('#topic-followup-planner').before(followupChartChoice);
const consultThemeStart=node('section',undefined,'consult-theme-start card');consultThemeStart.id='consult-theme-start';consultThemeStart.hidden=true;
consultThemeStart.innerHTML='<span class="badge">微运与年运盘固定启用</span><h2>你想先从哪个主题开始？</h2><p class="hint">先选主题，再自行勾选1–5张重点分盘。未勾选的分盘不会进入本轮AI上下文。</p><div class="consult-theme-grid"><label><input type="radio" name="consult-theme" value="理解自己"><span>理解自己<small>性格、需求与反复模式</small></span></label><label><input type="radio" name="consult-theme" value="关系与亲密"><span>关系与亲密<small>互动、承诺与关系选择</small></span></label><label><input type="radio" name="consult-theme" value="事业与学习"><span>事业与学习<small>方向、能力与现实发展</small></span></label><label><input type="radio" name="consult-theme" value="财富与资源"><span>财富与资源<small>收入、资源与长期取舍</small></span></label><label><input type="radio" name="consult-theme" value="当前阶段"><span>当前阶段<small>大运小运与眼前重点</small></span></label><label><input type="radio" name="consult-theme" value="选择与行动"><span>选择与行动<small>具体问题与下一步判断</small></span></label></div><h3>选择本轮重点分盘</h3><div class="research-chart-choice locked-chart-choice"><input type="checkbox" checked disabled><span><b>微运＋年运盘</b><small>固定启用 · 始终参与时间判断 · 不占选择数量</small></span></div><div id="consult-chart-choices" class="research-charts"></div><p id="consult-chart-count" class="hint"></p><button id="consult-theme-start-button" class="primary" type="button">进入连续咨询 ↗</button><p id="consult-theme-status" class="hint" role="status"></p>';
$('#experience-chat').before(consultThemeStart);
const followupQuestionNodes=[$('#topic-followup-planner'),$('#consult-messages'),$('#experience-chat').querySelector('label[for="consult-question"]'),$('#consult-question'),$('#topic-refined'),$('#consult-send'),$('#consult-chat-status'),$('#consult-chat-status').nextElementSibling];
function showFollowupQuestionStage(show){for(const item of followupQuestionNodes)if(item)item.hidden=!show}
function chartLabel(id){const row=chartChoices.find(x=>x[0]===id);return row?row[1]+' · '+row[2]:id}
 function chartCount(){const n=chosenCharts.size;$('#chart-choice-count').textContent=experiencePlan==='single'?'已选 '+n+' / 1 张盘':'已选 '+n+' 张图谱 · 请选择2–5张'}
function drawChartChoices(){
 const box=$('#research-charts');box.replaceChildren();
 for(const [id,label,purpose] of chartChoices.filter(x=>experiencePlan!=='single'||x[0]!=='annual')){
  const line=node('label',undefined,'research-chart-choice'),input=document.createElement('input');input.type=experiencePlan==='single'?'radio':'checkbox';input.name='experience-chart';input.value=id;input.checked=chosenCharts.has(id);
  input.onchange=()=>{if(experiencePlan==='single')chosenCharts=new Set([id]);else if(input.checked){if(chosenCharts.size>=5){input.checked=false;toast('最多选择5张图谱');return}chosenCharts.add(id)}else chosenCharts.delete(id);chartCount();$('#research-report').hidden=true;experienceReportReady=false;$('#experience-chat').hidden=true};
  const copy=node('span');copy.append(node('b',label),node('small',purpose));line.append(input,copy);box.append(line);
 }chartCount();
}
function drawFollowupChartChoices(){
 const box=$('#followup-charts');box.replaceChildren();
 for(const [id,label,purpose] of chartChoices){
  const line=node('label',undefined,'research-chart-choice'),input=document.createElement('input');input.type='checkbox';input.name='followup-chart';input.value=id;input.checked=chosenCharts.has(id);
  input.onchange=()=>{if(input.checked){if(chosenCharts.size>=5){input.checked=false;toast('最多选择5张图谱');return}chosenCharts.add(id)}else chosenCharts.delete(id);updateFollowupChartSummary()};
  const copy=node('span');copy.append(node('b',label),node('small',purpose));line.append(input,copy);box.append(line);
 }
 updateFollowupChartSummary();
}
function drawConsultChartChoices(){
 const box=$('#consult-chart-choices');if(!box)return;box.replaceChildren();
 for(const [id,label,purpose] of chartChoices){
  const line=node('label',undefined,'research-chart-choice'),input=document.createElement('input');input.type='checkbox';input.name='consult-chart';input.value=id;input.checked=chosenCharts.has(id);
  input.onchange=()=>{if(input.checked){if(chosenCharts.size>=5){input.checked=false;toast('最多选择5张分盘');return}chosenCharts.add(id)}else chosenCharts.delete(id);updateConsultChartCount()};
  const copy=node('span');copy.append(node('b',label),node('small',purpose));line.append(input,copy);box.append(line);
 }
 updateConsultChartCount();
}
function updateConsultChartCount(){const box=$('#consult-chart-count');if(box)box.textContent='已选 '+chosenCharts.size+' 张分盘 · 请选择1–5张；微运与年运盘固定启用'}
function updateFollowupChartSummary(){
 const labels=[...chosenCharts].map(chartLabel),text=labels.length?labels.join('、'):'尚未选择';
 $('#followup-chart-summary').textContent='当前沿用：'+text+(consultSessionMode?'；微运与年运盘固定启用':'');$('#followup-chart-count').textContent='已选 '+chosenCharts.size+' 张图谱 · '+(consultSessionMode?'请选择1–5张':'请选择2–5张');
}
function enterFollowupMode(){
 continueAfterReport.hidden=true;$('#research-flow').hidden=true;$('#consult-opening').hidden=true;consultThemeStart.hidden=true;$('#experience-chat').hidden=false;followupChartChoice.hidden=experiencePlan==='single';$('#followup-chart-panel').hidden=true;showFollowupQuestionStage(true);$('#topic-followup-planner').hidden=false;
 $('#experience-title').textContent=consultSessionMode?'连续AI咨询':'专题追问空间';$('#experience-intro').textContent=consultSessionMode?'每轮只读取你勾选的分盘、固定微运年运盘及紧邻的上一轮问答。':'完整报告已保存到「我的报告」。这里从一个新问题继续，不再重复展示长报告。';
 if(experiencePlan!=='single')drawFollowupChartChoices();$('#followup-locked-timing').hidden=!consultSessionMode;$('#followup-chart-help').textContent=consultSessionMode?'请选择1–5张重点分盘；微运与年运盘固定启用且不可取消。更换后从下一问起生效。':'请选择2–5张图谱。确认后才进入问题描述；本轮将生成约500字的追问回答，不会重复生成首份长报告。';updateRoundCount();loadFollowupPlan(consultSessionMode?'consult':experiencePlan);window.scrollTo({top:$('#experience').offsetTop,behavior:'smooth'});
}
continueAfterReport.onclick=enterFollowupMode;
$('#followup-keep-charts').onclick=()=>{$('#followup-chart-panel').hidden=true;topicReselecting=false;showFollowupQuestionStage(true);$('#topic-followup-planner').hidden=false;$('#consult-question').focus();$('#consult-chat-status').textContent='已沿用当前分盘。请选择推荐问题或直接输入你的问题。'};
$('#followup-change-charts').onclick=()=>{topicReselecting=true;showFollowupQuestionStage(false);followupChartChoice.hidden=false;$('#followup-chart-panel').hidden=false;drawFollowupChartChoices();$('#followup-chart-panel').scrollIntoView({behavior:'smooth',block:'start'});};
$('#followup-confirm-charts').onclick=()=>{const minimum=consultSessionMode?1:2;if(chosenCharts.size<minimum||chosenCharts.size>5){$('#followup-chart-count').textContent='请先选择'+minimum+'–5张图谱';return}if(consultSessionMode&&consultRequest)consultRequest={...consultRequest,selectedCharts:[...chosenCharts]};$('#followup-chart-panel').hidden=true;showFollowupQuestionStage(true);$('#topic-followup-planner').hidden=false;updateFollowupChartSummary();loadFollowupPlan(consultSessionMode?'consult':'topic');$('#consult-chat-status').textContent='已更换本轮重点分盘；微运与年运盘继续固定启用。现在请选择推荐问题或输入新的问题。';$('#consult-question').focus()};
function recommendation(question){
 if(/事业|工作|职业|换岗|创业|升职|收入/.test(question))return {ids:['d1','d10','d2','d9'],theme:'事业、收入与长期发展'};
 if(/感情|关系|伴侣|结婚|分手|复合|恋爱/.test(question))return {ids:['d1','d9','d12'],theme:'关系、承诺与家庭背景'};
 if(/学业|学习|考试|留学|读书/.test(question))return {ids:['d1','d24','d9'],theme:'学习、长期方向与当前阶段'};
 if(/房|搬家|居住/.test(question))return {ids:['d1','d4','d2'],theme:'安居与资源安排'};
 return {ids:['d1','d9'],theme:'整体需求、内在方向与当前阶段'};
}
function updateRoundCount(){const max=experiencePlans[experiencePlan].limit;$('#consult-round-count').textContent=experiencePlan==='consult'?'本次咨询 '+experienceRounds+' / '+max:'本次追问 '+experienceRounds+' / '+max;$('#consult-send').disabled=experienceRounds>=max}
function showUpgrade(){
 const box=$('#experience-upgrade');box.replaceChildren();box.hidden=true;
}
function suggestionQuestions(){
 const question=$('#research-question').value;
 const matched=recommendation(question).theme;
 // Theme-matched examples; personalized recommendations require actual chart analysis.
 const questions=matched.startsWith('事业')?['我目前最值得投入的事业方向是什么？','收入与长期发展之间，我最需要看清什么？','当前阶段哪些变化值得留意？']:matched.startsWith('关系')?['我的关系模式里最容易反复出现什么问题？','我对长期关系最重要的需求是什么？','当前阶段的感情变化有哪些判断边界？']:['我目前最值得投入的事业方向是什么？','我的关系模式里最容易反复出现什么问题？','未来一段时间我最应该关注什么？'];
 const box=$('#consult-suggestions');box.replaceChildren();for(const q of questions){const b=node('button',q,'suggestion-question');b.type='button';b.onclick=()=>{$('#consult-question').value=q;$('#consult-question').focus()};box.append(b)}
}
function openExperience(plan){
 topicSessionMode=false;topicRequest=null;topicReselecting=false;consultSessionMode=false;consultRequest=null;window.currentTopicRequest=null;$('#topic-followup-planner').hidden=true;
 continueAfterReport.hidden=true;followupChartChoice.hidden=true;$('#followup-chart-panel').hidden=true;consultThemeStart.hidden=plan!=='consult';
 $('#experience-mode-note').textContent='交互预览 · 不扣款、不调用AI。个性化内容将在正式分析后生成。';
 $('#experience-consent-copy').textContent='我知道这是流程预览，尚未生成针对我的AI分析。';
 $('#research-report-badge').textContent='报告结构预览';$('#research-outline').hidden=false;$('#research-preview-note').hidden=false;$('#topic-real-report').hidden=true;$('#topic-real-report').replaceChildren();$('#consult-send').textContent='预览本轮对话';
 if(!experiencePlans[plan])return;
 experiencePlan=plan;experienceRounds=0;experienceReportReady=false;
 const p=experiencePlans[plan];$('#experience-title').textContent=p.title;$('#experience-intro').textContent=p.intro;
 $('#research-flow').hidden=plan==='consult';$('#consult-opening').hidden=true;$('#experience-chat').hidden=true;$('#research-report').hidden=true;
 $('#experience-consent').checked=!!loggedIn;$('#research-error').textContent='';$('#consult-messages').replaceChildren();$('#consult-chat-status').textContent='';$('#consult-question').value='';
 $('#chat-heading').textContent=plan==='consult'?'继续聊聊你':'继续追问你的问题';
 $('#consult-context-note').textContent=plan==='consult'?'自行选择1–5张重点分盘 · 微运与年运盘固定启用 · 仅承接上一轮问答。':'初始报告之后，在同一主题下继续追问。当前为交互预览。';
 $('#chart-choice-title').textContent=plan==='single'?'选择1张指定盘':'选择2–5张你希望联合分析的图谱';
 $('#chart-choice-help').textContent=plan==='single'?'围绕这张盘回答一个具体问题。':'选择2–5张本命或辅助分盘；所选年份的年度独立盘会自动结合，不占选择数量。';
 $('#recommend-charts').hidden=plan!=='topic';$('#recommendation-note').textContent='';
 $('#research-generate').textContent=plan==='single'?'预览简洁解读结构':'预览多图谱综合报告结构';
 chosenCharts=new Set(plan==='single'?['d10']:plan==='consult'?[]:['d1','d10','d2']);drawChartChoices();if(plan==='consult')drawConsultChartChoices();updateRoundCount();suggestionQuestions();showUpgrade();location.hash='experience';go('experience');
 if((plan==='single'||plan==='topic')&&loggedIn)prepareTopicExperience().catch(e=>$('#research-error').textContent=e.message);
 if(plan==='consult'&&loggedIn)prepareConsultExperience().catch(e=>$('#consult-chat-status').textContent=e.message);
}
$('#recommend-charts').onclick=()=>{
 const q=$('#research-question').value.trim();if(!q){$('#research-error').textContent='先写下你想了解的问题，再让星序推荐。';return}
 const result=recommendation(q);chosenCharts=new Set(result.ids);drawChartChoices();$('#recommendation-note').textContent='针对'+result.theme+'，建议联合：'+result.ids.map(chartLabel).join('、')+'。请确认或调整。当前按主题匹配展示推荐示例，尚未调用AI。';$('#research-error').textContent='';
};
$('#research-generate').onclick=()=>{
 if(topicSessionMode){busy($('#research-generate'),generateTopicReport);return}

 const q=$('#research-question').value.trim(),n=chosenCharts.size;
 if(!q||!$('#experience-consent').checked||(experiencePlan==='topic'&&(n<2||n>5))||(experiencePlan==='single'&&n!==1)){$('#research-error').textContent='请填写问题、确认预览说明，并选择符合数量要求的图谱。';return}
 $('#research-error').textContent='';experienceReportReady=true;$('#research-report').hidden=false;
 $('#research-report-title').textContent=experiencePlan==='single'?'单项简洁解读':'多图谱综合报告';$('#research-report-question').textContent='你的问题：'+q;$('#research-report-charts').textContent='本次选用：'+[...chosenCharts].map(chartLabel).join('、');$('#experience-chat').hidden=false;showUpgrade();
};
$('#ask-own-question').onclick=()=>{$('#consult-question').focus()};
$('#consult-send').onclick=()=>{
 if(topicSessionMode){busy($('#consult-send'),sendTopicFollowup);return}
 if(consultSessionMode){if(!experienceReportReady){$('#consult-chat-status').textContent='请先选择一个主题进入咨询。';return}busy($('#consult-send'),sendConsultFollowup);return}

 const q=$('#consult-question').value.trim(),max=experiencePlans[experiencePlan].limit;if(!q){$('#consult-chat-status').textContent='先写下你的问题。';return}if(experienceRounds>=max)return;
 if(experiencePlan!=='consult'&&!experienceReportReady){$('#consult-chat-status').textContent='请先完成报告结构预览。';return}
 const box=$('#consult-messages'),pair=node('section',undefined,'consult-pair');pair.append(node('p',q,'consult-user'),node('p','AI回复区域预览：正式版将在此结合你勾选的分盘、固定微运年运与上一轮问答。这不是针对你的实际分析。','consult-answer'));box.append(pair);
 experienceRounds++;$('#consult-question').value='';updateRoundCount();$('#consult-chat-status').textContent='已演示1轮对话，仅更新预览计数，未调用AI或消耗真实权益。';showUpgrade();
};

let topicSessionMode=false,topicRequest=null,topicReselecting=false;window.currentTopicRequest=null;
let consultSessionMode=false,consultRequest=null;
window.consultSelectedCharts=()=>[...chosenCharts];
function enableTopicMode(){
 topicSessionMode=true;
 const single=experiencePlan==='single';
 $('#experience-mode-note').textContent=single?'单项解读权益 · 成功生成简洁报告扣1次权益；包含2轮追问。':'专题体验权益 · 实际AI解读：成功生成报告扣1次权益；5轮追问包含在本份报告内。';
 $('#experience-consent-copy').textContent='同意将选定图谱、本命、运限、问题及后续对话发送至AI服务生成解读。';
 $('#research-generate').textContent=single?'使用1次权益 · 生成单项解读':'使用1次权益 · 生成综合报告';$('#consult-send').textContent=single?'发送单项追问':'发送专题追问';
}
async function prepareTopicExperience(){
 const rights=await refreshEntitlements();
 if(!['single','topic'].includes(experiencePlan)||experienceReportReady)return;
 if((rights?.[experiencePlan]||0)>0)enableTopicMode();
}
function displayTopicReport(text,question,charts){
 experienceReportReady=true;$('#research-report').hidden=false;$('#research-report-badge').textContent='已生成并保存';
 $('#research-report-title').textContent=experiencePlan==='single'?'AI单项解读':'多盘专题综合报告';$('#research-report-question').textContent='你的问题：'+question;
 $('#research-report-charts').textContent='选定图谱：'+charts.map(chartLabel).join('、');
 $('#research-outline').hidden=true;$('#research-preview-note').hidden=true;$('#topic-real-report').hidden=false;
 renderReading($('#topic-real-report'),text);$('#experience-chat').hidden=true;$('#topic-followup-planner').hidden=true;continueAfterReport.hidden=!topicSessionMode;updateRoundCount();if(topicSessionMode){$('#topic-plan-questions').replaceChildren();$('#topic-refined').hidden=true}
 $('#topic-reselect').hidden=true;
 if(topicSessionMode&&!topicReselecting)$('#research-charts').hidden=true;
 $('#experience-upgrade').hidden=true;
}
async function generateTopicReport(){
 if(!loggedIn)throw Error('请先登录');if(!session)throw Error('请先创建或打开一张星盘');
 const question=$('#research-question').value.trim(),charts=[...chosenCharts];
 const validCharts=experiencePlan==='single'?charts.length===1:charts.length>=2&&charts.length<=5;
 if(!question||!validCharts||!$('#experience-consent').checked)throw Error(experiencePlan==='single'?'请填写问题、选择1张图谱并同意数据处理':'请填写问题、选择2–5张图谱并同意数据处理');
 const token=session;
 const body={session:token,kind:experiencePlan,round:1,question,topicQuestion:question,selectedCharts:charts,year:Number($('#year').value),consent:true};
 $('#research-error').textContent='正在联合分析，通常需1–2分钟；请勿关闭页面。失败不扣权益。';
 try{const result=await requestReading(body);if(session!==token)return;
 topicRequest={...body,topicBaseScope:result.topicScope||body.topicBaseScope};window.currentTopicRequest=topicRequest;experienceRounds=(result.followups||[]).length;displayTopicReport(result.text,question,charts);$('#consult-messages').replaceChildren();
 $('#research-error').textContent='已生成并保存到我的解读报告。你可继续'+(experiencePlan==='single'?'2':'5')+'轮追问。';await refreshEntitlements();}
 catch(e){$('#research-error').textContent=e.message;throw e}
}
async function sendTopicFollowup(){
 if(!topicRequest||!experienceReportReady)throw Error('请先生成或恢复专题报告');
 const limit=experiencePlan==='single'?2:5;if(experienceRounds>=limit)throw Error('这份报告的'+limit+'轮追问已完成');
 if(!$('#experience-consent').checked)throw Error('请先同意专题数据处理说明');
 const question=$('#consult-question').value.trim();if(!question)throw Error('请输入问题');
 const token=session,charts=[...chosenCharts];if(experiencePlan==='single'?charts.length!==1:charts.length<2||charts.length>5)throw Error(experiencePlan==='single'?'请重新选择1张图谱':'请重新选择2–5张图谱');
 $('#consult-chat-status').textContent='正在结合本份专题及此前问答分析…';
 try{const result=await requestReading({...topicRequest,session:token,round:2,question,selectedCharts:charts});if(session!==token)return;
 const pair=node('section',undefined,'consult-pair');pair.append(node('p',question,'consult-user'));const answer=node('article',undefined,'reading-copy foldable-reading');pair.append(answer);$('#consult-messages').append(pair);renderReading(answer,result.text);
 topicRequest={...topicRequest,selectedCharts:charts};window.currentTopicRequest=topicRequest;topicReselecting=false;$('#research-charts').hidden=true;$('#followup-chart-panel').hidden=true;$('#research-report-charts').textContent='当前追问图谱：'+charts.map(chartLabel).join('、');updateFollowupChartSummary();
 experienceRounds=result.followups?result.followups.length:(experienceRounds+(result.cached?0:1));$('#consult-question').value='';updateRoundCount();$('#consult-chat-status').textContent='回答已保存；继续追问会沿用当前分盘。';loadFollowupPlan(experiencePlan);}
 catch(e){$('#consult-chat-status').textContent=e.message;throw e}
}
function restoreTopicReport(report){
 experiencePlan=report.product==='single'?'single':'topic';
 enableTopicMode();const req=report.topicRequest;
 topicRequest={...req,session,kind:experiencePlan,consent:true};window.currentTopicRequest=topicRequest;chosenCharts=new Set(req.selectedCharts);drawChartChoices();
 $('#research-question').value=req.topicQuestion;$('#experience-consent').checked=true;
 experienceRounds=report.followups.length;displayTopicReport(report.text,req.topicQuestion,req.selectedCharts);$('#consult-messages').replaceChildren();
 updateRoundCount();enterFollowupMode();
}
$('#topic-reselect').onclick=()=>{
 if(!topicSessionMode)return;
 $('#followup-change-charts').click();
};
function enableConsultMode(){
 consultSessionMode=true;
 $('#experience-mode-note').textContent='连续AI咨询权益 · 自选1–5张重点分盘；微运与年运盘固定启用。';
 $('#experience-consent-copy').textContent='同意将所选分盘、微运年运、本次问题及紧邻上一轮对话发送至AI服务生成咨询内容。';
 $('#consult-context-note').textContent='未勾选分盘不会进入AI上下文 · 微运与年运盘固定启用 · 只承接上一轮问答；失败与重试不扣轮数。';
 $('#consult-send').textContent='发送本轮问题';
}
async function prepareConsultExperience(){
 const rights=await refreshEntitlements();
 if(experiencePlan==='consult'&&!experienceReportReady&&rights?.consult>0)enableConsultMode();
}
async function startConsultChat(){
 if(!loggedIn)throw Error('请先登录');if(!session)throw Error('请先创建或打开一张星盘');
 const selected=document.querySelector('input[name="consult-theme"]:checked');if(!selected)throw Error('请先选择一个想探索的主题');
 const charts=[...chosenCharts];if(charts.length<1||charts.length>5)throw Error('请先选择1–5张重点分盘；微运与年运盘已固定启用');
 $('#consult-theme-status').textContent='正在开启连续咨询…';const token=session;
 try{const year=Number($('#year').value)||new Date().getFullYear();const result=await api('consult/start',{session:token,theme:selected.value,selectedCharts:charts,year,consent:true});if(session!==token)return;consultRequest={session:token,kind:'consult',round:1,selectedCharts:result.selectedCharts||charts,year,consent:true};chosenCharts=new Set(consultRequest.selectedCharts);experienceReportReady=true;experienceRounds=result.usedRounds||0;$('#consult-messages').replaceChildren();$('#topic-plan-direction').value=selected.value;enterFollowupMode();$('#consult-chat-status').textContent='已选择“'+selected.value+'” · 重点分盘：'+[...chosenCharts].map(chartLabel).join('、')+'；微运与'+year+'年运盘固定启用。';await refreshEntitlements()}
 catch(e){$('#consult-theme-status').textContent=e.message;throw e}
}
$('#consult-theme-start-button').onclick=e=>busy(e.currentTarget,startConsultChat);
async function sendConsultFollowup(){
 if(!consultRequest||!experienceReportReady)throw Error('请先选择主题与分盘进入咨询');if(experienceRounds>=30)throw Error('本次30轮连续咨询已完成');if(!$('#experience-consent').checked)throw Error('请先同意咨询数据处理说明');
 const question=$('#consult-question').value.trim(),charts=[...chosenCharts];if(!question)throw Error('请输入问题');if(charts.length<1||charts.length>5)throw Error('请先选择1–5张重点分盘');const token=session;$('#consult-chat-status').textContent='正在结合所选分盘、微运年运与上一轮问答…';
 try{const result=await requestReading({...consultRequest,session:token,round:2,question,selectedCharts:charts,year:Number($('#year').value)});if(session!==token)return;const pair=node('section',undefined,'consult-pair');pair.append(node('p',question,'consult-user'));const answer=node('article',undefined,'reading-copy foldable-reading');pair.append(answer);$('#consult-messages').append(pair);renderReading(answer,result.text);renderConsultKeywords(pair,result.keywords||[]);consultRequest={...consultRequest,selectedCharts:charts};experienceRounds=result.followups?result.followups.length:(experienceRounds+(result.cached?0:1));$('#consult-question').value='';updateRoundCount();$('#consult-chat-status').textContent='本轮回答已保存 · '+experienceRounds+' / 30；下一问只承接这一轮。';loadFollowupPlan('consult');}
 catch(e){$('#consult-chat-status').textContent=e.message;throw e}
}
function renderConsultKeywords(container,keywords){
 if(!keywords.length)return;const box=node('div',undefined,'consult-keyword-suggestions');box.append(node('small','沿着关键词继续问：'));
 for(const keyword of keywords){const button=node('button',keyword,'suggestion-question');button.type='button';button.onclick=()=>{$('#consult-question').value='我想继续了解“'+keyword+'”对我当前问题的具体影响。';$('#consult-question').focus()};box.append(button)}container.append(box);
}
function restoreConsultReport(report){
 enableConsultMode();const saved=report.consultRequest||{};chosenCharts=new Set(saved.selectedCharts?.length?saved.selectedCharts:['d1']);consultRequest={session,kind:'consult',round:1,selectedCharts:[...chosenCharts],year:saved.year||Number($('#year').value)||new Date().getFullYear(),consent:true};$('#experience-consent').checked=true;experienceReportReady=true;experienceRounds=(report.followups||[]).length;$('#consult-messages').replaceChildren();enterFollowupMode();
}
$('#topic-plan-refresh').onclick=()=>loadFollowupPlan(consultSessionMode?'consult':experiencePlan,Boolean($('#consult-question').value.trim()));
$('#topic-plan-direction').onchange=()=>loadFollowupPlan(consultSessionMode?'consult':experiencePlan,Boolean($('#consult-question').value.trim()));
$('#consult-question').addEventListener('input',()=>{if(topicSessionMode||consultSessionMode)queueDraftRefinement(consultSessionMode?'consult':experiencePlan)});
$('#experience-consent').addEventListener('change',e=>{if(e.target.checked&&experienceReportReady&&(topicSessionMode||consultSessionMode))loadFollowupPlan(consultSessionMode?'consult':experiencePlan)});
// A direct preview URL has a meaningful opening rather than an empty screen.
if(location.hash==='#experience')openExperience('consult');
