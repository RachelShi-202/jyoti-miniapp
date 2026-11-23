'use strict';
(()=>{
 const workbench=/^\/(studio|ipad)\/?$/.test(location.pathname);
 if(!workbench)return;
 document.documentElement.classList.add('workspace-mode');
 document.body.classList.add('workspace-mode');
 document.title='星序 JYOTI · 专业排盘工作台';
 const entry=document.querySelector('.view-entry');if(entry)entry.textContent='切换浏览方式';
 const shell=document.querySelector('.phone'),header=shell?.querySelector('header');
 if(!shell||!header)return;
 const top=document.createElement('div');top.className='workspace-topbar';
 const copy=document.createElement('div');copy.className='workspace-topbar-copy';
 const kicker=document.createElement('span');kicker.textContent='PROFESSIONAL CHARTING DESK';
 const title=document.createElement('strong');title.textContent='专业排盘工作台';copy.append(kicker,title);
 const tools=document.createElement('div');tools.className='workspace-tools';
 const status=document.createElement('span');status.className='workspace-status';status.textContent='账号、星盘与手机端同步';
 const switchLink=document.createElement('a');switchLink.href='/view';switchLink.className='workspace-switch';switchLink.textContent='切换浏览方式';
 tools.append(status,switchLink);top.append(copy,tools);header.after(top);
 const nav=document.querySelector('nav');
 if(nav){
  const note=document.createElement('p');note.className='workspace-nav-note';note.textContent='同一账号 · 同一数据 · 同一支付权益';nav.append(note);
 }
 const updateMode=()=>document.body.dataset.workspaceViewport=innerWidth<=1024?'tablet':'desktop';
 updateMode();addEventListener('resize',updateMode,{passive:true});
})();
