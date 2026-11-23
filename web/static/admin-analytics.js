(()=>{
  'use strict';
  const $=id=>document.getElementById(id);
  const loginShell=$('login-shell'),dashboard=$('dashboard'),loading=$('loading');
  const labels={annual:'年度报告',single:'单项解读',topic:'多盘专题',consult:'全盘咨询',natal:'本命报告',wechat:'微信',alipay:'支付宝',paypal:'PayPal',paid:'已支付',pending:'待支付',failed:'失败',refunded:'已退款'};
  let days=30;

  const number=value=>new Intl.NumberFormat('zh-CN').format(Number(value||0));
  const dateTime=value=>value?new Intl.DateTimeFormat('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value*1000)):'—';
  const safeLabel=key=>labels[key]||String(key).slice(0,18);

  async function api(path,options={}){
    const response=await fetch(path,{...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});
    let data={};
    try{data=await response.json()}catch(_){data={detail:'服务返回异常'}}
    if(!response.ok){const error=new Error(data.detail||'请求失败');error.status=response.status;throw error}
    return data;
  }

  function showLogin(message=''){
    dashboard.hidden=true;loginShell.hidden=false;$('login-error').textContent=message;
    setTimeout(()=>$('admin-token').focus(),50);
  }

  function showDashboard(){loginShell.hidden=true;dashboard.hidden=false}

  function setText(id,value){$(id).textContent=value}

  function pathFor(values,width,height,pad,max){
    if(!values.length)return '';
    const usableW=width-pad*2,usableH=height-pad*2,step=values.length>1?usableW/(values.length-1):0;
    return values.map((value,index)=>`${index?'L':'M'} ${(pad+index*step).toFixed(1)} ${(height-pad-(Number(value||0)/max)*usableH).toFixed(1)}`).join(' ');
  }

  function lineChart(targetId,rows,series){
    const target=$(targetId);target.replaceChildren();
    if(!rows.length||!series.some(item=>rows.some(row=>Number(row[item.key]||0)>0))){
      const empty=document.createElement('div');empty.className='chart-empty';empty.textContent='该时段暂无数据';target.append(empty);return;
    }
    const ns='http://www.w3.org/2000/svg',width=720,height=220,pad=28;
    const all=series.flatMap(item=>rows.map(row=>Number(row[item.key]||0)));const max=Math.max(1,...all);
    const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.setAttribute('role','img');
    [0,.25,.5,.75,1].forEach((ratio,index)=>{
      const y=pad+ratio*(height-pad*2),line=document.createElementNS(ns,'line');
      line.setAttribute('x1',pad);line.setAttribute('x2',width-pad);line.setAttribute('y1',y);line.setAttribute('y2',y);line.setAttribute('class','grid-line');svg.append(line);
      if(index<4){const text=document.createElementNS(ns,'text');text.setAttribute('x',0);text.setAttribute('y',y+3);text.setAttribute('class','chart-label');text.textContent=Math.round(max*(1-ratio));svg.append(text)}
    });
    series.forEach((item,index)=>{const path=document.createElementNS(ns,'path');path.setAttribute('d',pathFor(rows.map(row=>row[item.key]),width,height,pad,max));path.setAttribute('class',index===0?'series-primary':'series-secondary');svg.append(path)});
    const labelIndexes=[0,Math.floor((rows.length-1)/2),rows.length-1];
    labelIndexes.forEach((rowIndex,index)=>{const text=document.createElementNS(ns,'text');text.setAttribute('x',index===0?pad:index===1?width/2:width-pad);text.setAttribute('text-anchor',index===0?'start':index===1?'middle':'end');text.setAttribute('y',height-2);text.setAttribute('class','chart-label');text.textContent=rows[rowIndex].date.slice(5);svg.append(text)});
    target.append(svg);
  }

  function bars(targetId,items){
    const target=$(targetId);target.replaceChildren();const entries=Object.entries(items||{}).filter(([,value])=>Number(value)>0).sort((a,b)=>b[1]-a[1]);
    if(!entries.length){const empty=document.createElement('div');empty.className='bars-empty';empty.textContent='该时段暂无数据';target.append(empty);return}
    const max=Math.max(...entries.map(([,value])=>Number(value)));
    entries.forEach(([key,value])=>{
      const row=document.createElement('div');row.className='bar-row';
      const label=document.createElement('span');label.className='bar-label';label.textContent=safeLabel(key);
      const track=document.createElement('div');track.className='bar-track';const fill=document.createElement('div');fill.className='bar-fill';fill.style.width=`${Math.max(2,Number(value)/max*100)}%`;track.append(fill);
      const count=document.createElement('strong');count.className='bar-value';count.textContent=number(value);
      row.append(label,track,count);target.append(row);
    });
  }

  function render(data){
    const period=`近 ${data.periodDays} 天`;
    setText('period-label',period);
    setText('kpi-users',number(data.users.total));setText('kpi-users-detail',`${period}新增 ${number(data.users.newInPeriod)} · 邮箱 ${number(data.users.emailVerified)} · 手机 ${number(data.users.phoneVerified)}`);
    setText('kpi-active',number(data.activity.activeInPeriod));setText('kpi-active-detail',`今日 DAU ${number(data.activity.dau)} · 30日 MAU ${number(data.activity.mau30Days)}`);
    setText('kpi-paid-users',number(data.orders.paidUsersInPeriod));setText('kpi-paid-users-detail',`${period}支付 ${number(data.orders.paidInPeriod)} 单 · 累计付费用户 ${number(data.orders.paidUsers)}`);
    setText('kpi-cny',`¥${data.gmv.periodNet.cnyYuan}`);setText('kpi-cny-detail',`累计净成交 ¥${data.gmv.net.cnyYuan} · 已退款 ¥${data.gmv.refunded.cnyYuan}`);
    setText('kpi-usd',`$${data.gmv.periodNet.usd}`);setText('kpi-usd-detail',`累计净成交 $${data.gmv.net.usd} · 已退款 $${data.gmv.refunded.usd}`);
    setText('kpi-reports',number(data.reports.createdInPeriod));setText('kpi-reports-detail',`累计 ${number(data.reports.total)} 份 · 报告用户 ${number(data.reports.creators)}`);
    setText('updated-at',`更新于 ${dateTime(data.generatedAt)}`);
    const started=data.activity.trackingStartedAt?new Date(data.activity.trackingStartedAt*1000).toLocaleDateString('zh-CN'):'尚未开始';
    setText('tracking-note',`活跃追踪自 ${started} 起累计；历史活跃数据不会倒推。`);
    lineChart('activity-chart',data.daily,[{key:'activeUsers'},{key:'newUsers'}]);
    lineChart('output-chart',data.daily,[{key:'reports'},{key:'paidOrders'}]);
    bars('product-bars',data.orders.byProductInPeriod);bars('channel-bars',data.orders.byChannelInPeriod);bars('report-bars',data.reports.byProductInPeriod);
  }

  async function load(){
    loading.hidden=false;
    try{const data=await api(`/api/admin/analytics/summary?days=${days}`);showDashboard();render(data)}
    catch(error){if(error.status===401)showLogin();else showLogin(error.message)}
    finally{loading.hidden=true}
  }

  $('login-form').addEventListener('submit',async event=>{
    event.preventDefault();const input=$('admin-token');$('login-error').textContent='';
    try{await api('/api/admin/analytics/login',{method:'POST',body:JSON.stringify({token:input.value})});input.value='';await load()}
    catch(error){input.value='';$('login-error').textContent=error.message;input.focus()}
  });
  $('period-switch').addEventListener('click',event=>{
    const button=event.target.closest('button[data-days]');if(!button)return;
    days=Number(button.dataset.days);document.querySelectorAll('#period-switch button').forEach(item=>item.classList.toggle('active',item===button));load();
  });
  $('refresh-button').addEventListener('click',load);
  $('logout-button').addEventListener('click',async()=>{try{await api('/api/admin/analytics/logout',{method:'POST',body:'{}'})}finally{showLogin('已安全退出')}});
  load();
})();
