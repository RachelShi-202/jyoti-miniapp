"use strict";
window.rectificationReady=new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='/static/rectification.js?v=20261117-entry-v11';script.onload=resolve;script.onerror=()=>reject(Error('出生时间校准页面加载失败'));document.head.append(script)});
// Display prices are informative; checkout always uses the server-owned catalogue.
const products=[
 {id:'free',name:'免费本命盘解读',fen:0,tag:'先认识你的星盘',description:'从本命盘AI解读开始，认识你的性格、特质与人生亮点。年运另购。',includes:['本命盘排盘','本命盘AI首轮解读 · 每账号免费一次'],cta:'开始免费体验'},
 {id:'annual',name:'印占年运报告',fen:290,tag:'看清年度阶段变化',description:'分析未来三年阶段变化，以及所选年度事业、财富、感情与健康的主要趋势。',includes:['1份所选年度深度报告','未来三年阶段脉络','五大生活领域分析','年度机会、风险与行动建议','已生成报告可重复查看'],cta:'购买印占年运报告'},
 {id:'single',name:'单项解读',fen:490,tag:'聚焦一个具体问题',description:'指定 1 张图谱并写下问题，获得一份简洁解读，再继续追问。',includes:['1 张指定图谱','简洁报告＋2 次追问','报告与追问自动保存'],cta:'购买单项解读'},
 {id:'topic',name:'多维综合解读',fen:1990,tag:'跨盘联动的深度研究',description:'围绕一个复杂问题，自选 2–5 张图谱，获得多维联动的综合报告。',includes:['自选 2–5 张图谱','深度综合报告','5 轮连续追问'],cta:'购买多维解读'},
 {id:'consult',name:'全盘系统分析',fen:2990,tag:'完整而连续的探索',description:'选择重点分盘并固定结合微运与年运盘，在同一个空间持续探索。',includes:['重点分盘＋微运年运','30 轮连续 AI 咨询','报告与对话自动保存'],cta:'购买全盘分析'},
 {id:'explorer_starter',name:'探索体验包',fen:990,tag:'第一次完整体验',description:'从年度趋势，到一个具体问题，再用3次追问把答案问清楚。',valueTitle:'一次体验三种探索方式',path:'看全年 → 解一题 → 追问3次',includes:['年度趋势报告 1份','单项聚焦解读 1份','本命报告延伸问答 3轮'],benefits:[['年度趋势报告','1份'],['单项聚焦解读','1份'],['本命报告延伸问答','3轮']],cta:'¥9.9 开启完整体验'},
 {id:'explorer_deep',name:'深度探索包',fen:3990,tag:'核心推荐 · 适合多个问题',description:'先掌握全年节奏，再分别拆解3个关键问题，最后用多维综合解读串联全局。',valueTitle:'5份独立解读权益',path:'看全年 → 解3题 → 多维串联',includes:['年度趋势报告 1份','单项聚焦解读 3份','多维综合解读 1份'],benefits:[['年度趋势报告','1份'],['单项聚焦解读','3份'],['多维综合解读','1份']],cta:'¥39.9 开启深度探索'},
 {id:'rectification',name:'出生时间校准',fen:3990,tag:'多维资料 · 专业校准',description:'通过出生资料、个人外在特征、人生经历及恋爱婚姻关系等多维度信息，结合吠陀占星体系，对出生时间进行交叉验证，提供核心参考时间及专业校准报告。',includes:['六阶段资料采集','草稿云端保存 · 跨设备继续','核心参考时间与专业校准报告'],cta:'了解出生时间校准'}
];
const paymentNames={alipay:'支付宝',wechat:'微信支付',paypal:'PayPal'};
// PayPal hosted payment links. Each link has a fixed USD amount configured in PayPal.
const paypalLinks={annual:'https://www.paypal.com/ncp/payment/WM83P8WY8Q2FC',single:'https://www.paypal.com/ncp/payment/N5RG5DLTQYNU8',topic:'https://www.paypal.com/ncp/payment/AFX9ZY4XP85LL',consult:'https://www.paypal.com/ncp/payment/RACHMJEGP5LFL'};
const paypalPrices={annual:'$1.00 USD',single:'$4.90 USD',topic:'$19.90 USD',consult:'$29.90 USD',explorer_starter:'$9.90 USD',explorer_deep:'$39.90 USD',rectification:'$39.90 USD'};
let checkoutProductId='annual';
let upgradeSource='';
let annualPurchaseYear=new Date().getFullYear();
let annualManualYear=false;
const yearField=$('#year');if(yearField)yearField.value=String(annualPurchaseYear);
if(yearField){const yearLabel=yearField.closest('label');if(yearLabel){yearLabel.hidden=true;yearLabel.style.display='none';yearLabel.insertAdjacentHTML('afterend','<div class="annual-year-actions"><button id="annual-current-year" type="button" class="secondary">本年度（'+annualPurchaseYear+'）</button><button id="annual-other-year" type="button" class="text-button">其他年份</button></div><p class="hint annual-current-year">当前选择：'+annualPurchaseYear+'年。默认直接购买并生成本年度。</p>');const yearHint=$('.annual-current-year');$('#annual-current-year').onclick=()=>{annualManualYear=false;annualPurchaseYear=new Date().getFullYear();yearField.value=String(annualPurchaseYear);yearLabel.hidden=true;yearLabel.style.display='none';yearHint.textContent='当前选择：'+annualPurchaseYear+'年。默认直接购买并生成本年度。'};$('#annual-other-year').onclick=()=>{annualManualYear=true;yearLabel.hidden=false;yearLabel.style.display='';yearField.focus();yearHint.textContent='请选择需要生成报告的年份。'};yearField.addEventListener('input',()=>{annualManualYear=true;annualPurchaseYear=Number(yearField.value)||new Date().getFullYear();yearHint.textContent='当前选择：'+annualPurchaseYear+'年。'})}}
let paymentCapability={paymentReady:false,payableProducts:[],paymentChannels:{}};
const quoteFen=()=>selectedProduct().fen;
function priceText(product){return product.fen===0?'免费':'¥'+(product.fen%100?(product.fen/100).toFixed(1):String(product.fen/100))}
function selectedProduct(){return products.find(p=>p.id===checkoutProductId)||products[1]}
function selectedPayment(){return document.querySelector('input[name="payment-method"]:checked').value}
function updateCheckout(){
 const p=selectedProduct(),name=paymentNames[selectedPayment()];
 $('#checkout-title').textContent=p.name;$('#checkout-description').textContent=p.description;
 $('#checkout-includes').textContent=p.includes.join(' · ');$('#checkout-price').textContent=selectedPayment()==='paypal'?paypalPrices[p.id]||'PayPal':priceText(p);
 $('#checkout-credit').textContent='';
 $('#payment-selected').textContent='已选择'+name+(selectedPayment()==='paypal'?' · 美元付款':' · 人民币报价');
 const payable=paymentCapability.payableProducts?.includes(p.id);
 const channelReady=!!paymentCapability.paymentChannels?.[selectedPayment()];
 $('#payment-preview').textContent=channelReady&&payable?name+' · '+(selectedPayment()==='paypal'?(paypalPrices[p.id]||'PayPal'):priceText(p)):'该方式暂未开放';
 $('#checkout-experience').hidden=['annual','explorer_starter','explorer_deep','rectification'].includes(p.id);
 $('#payment-status').textContent=!payable?'该服务仍在完善交付流程，暂不创建订单。':(!channelReady?'所选支付方式尚未完成服务器密钥配置。':(selectedPayment()==='paypal'?'PayPal 将在新页面打开美元付款；支付成功后服务器自动核验并发放权益。':'金额由服务器核验；支付成功后权益自动进入当前账号。'));
}
function productButton(product,primary=false){const button=node('button',product.cta+' ↗',primary?'primary':'secondary');button.type='button';button.dataset.product=product.id;button.onclick=()=>openPricingProduct(product);return button}
function renderSingleProducts(){
 const box=$('#single-product-cards');
 for(const [index,id] of ['annual','single','topic','consult'].entries()){
  const product=products.find(item=>item.id===id),card=node('article',undefined,'single-product-card');
  card.append(node('span','0'+(index+1),'product-sequence'),node('span',product.tag,'pricing-kicker'),node('h2',product.name),node('strong',priceText(product),'pricing-price'),node('p',product.description,'pricing-description'));
  const list=node('ul');for(const line of product.includes)list.append(node('li',line));card.append(list,productButton(product));
  const preview=node('button','先看服务流程','text-button');preview.type='button';preview.onclick=()=>openExperience(product.id);if(id!=='annual')card.append(preview);box.append(card);
 }
}
function renderBundles(){
 const box=$('#bundle-product-cards');
 const intro=document.querySelector('[data-service-panel="bundles"] .service-panel-intro');if(intro){intro.querySelector('h2').textContent='一次购齐，按自己的节奏慢慢探索';intro.querySelector('p').textContent='把分散的单次服务组合成一条完整路径；权益独立计数、分次使用，余额还可累计。'}
 for(const id of ['explorer_starter','explorer_deep']){
  const product=products.find(item=>item.id===id),featured=id==='explorer_deep',card=node('article',undefined,'bundle-card'+(featured?' bundle-card-featured':''));
  if(featured)card.append(node('span','核心推荐 · 5份解读权益','recommend-ribbon'));
  const head=node('div',undefined,'bundle-card-head'),copy=node('div');copy.append(node('span',product.tag,'pricing-kicker'),node('h2',product.name));head.append(copy,node('strong',priceText(product),'bundle-price'));card.append(head,node('p',product.description,'pricing-description'));
  const value=node('div',undefined,'bundle-value');value.append(node('b',product.valueTitle),node('span',product.path));card.append(value);
  const benefits=node('div',undefined,'bundle-benefits');for(const [label,quantity] of product.benefits){const row=node('div');row.append(node('span',label),node('b',quantity));benefits.append(row)}
  card.append(benefits,productButton(product,featured),node('small','一次购齐 · 分次使用 · 可与已有余额累计','bundle-note'));box.append(card);
 }
}
function renderProfessional(){
 const product=products.find(item=>item.id==='rectification'),card=node('article',undefined,'professional-card');
 const visual=node('div',undefined,'precision-visual');visual.innerHTML='<span class="precision-ring"></span><span class="precision-axis"></span><b>12:03</b><small>± 05 MIN</small>';
 const copy=node('div',undefined,'professional-copy');copy.append(node('span','INDEPENDENT PROFESSIONAL SERVICE','pricing-kicker'),node('h2',product.name),node('strong',priceText(product),'professional-price'),node('p',product.description,'pricing-description'));
 const list=node('ul');for(const line of product.includes)list.append(node('li',line));copy.append(list,productButton(product,true),node('small','独立商品 ID · 独立订单关联','bundle-note'));card.append(visual,copy);$('#professional-product-card').append(card);
}
function renderHomeServices(){
 const box=document.querySelector('.home-service-grid');if(!box)return;
 const meta={
  explorer_deep:{tab:'bundles',badge:'核心推荐',summary:'年度趋势 1份 · 聚焦解读 3份 · 多维综合 1份'},
  explorer_starter:{tab:'bundles',badge:'完整体验',summary:'年度趋势 1份 · 聚焦解读 1份 · 延伸问答 3轮'},
  annual:{tab:'single',badge:'年度趋势',summary:'看清事业、财富、关系与生活节奏'},
  single:{tab:'single',badge:'聚焦问题',summary:'选择1张图谱，解读一个具体问题'},
  topic:{tab:'single',badge:'多维联动',summary:'自选2–5张图谱，获得综合报告'},
  consult:{tab:'single',badge:'连续探索',summary:'重点分盘＋微运年运 · 30轮咨询'},
  rectification:{tab:'professional',badge:'专业服务',summary:'多维资料交叉验证 · 专业校准报告'}
 },order=['explorer_deep','rectification','explorer_starter','annual','single','topic','consult'];
 box.classList.add('home-service-carousel');box.setAttribute('aria-label','全部星序服务');box.replaceChildren();
 for(const id of order){const product=products.find(item=>item.id===id),info=meta[id],card=node('button',undefined,'home-service-card home-service-slide'+(id==='explorer_deep'?' home-service-featured':'')+(id==='rectification'?' home-service-professional':''));card.type='button';card.dataset.go='pricing';card.dataset.serviceTab=info.tab;card.append(node('span',info.badge,'badge'),node('b',product.name),node('strong',priceText(product)),node('small',info.summary),node('i',info.tab==='professional'?'了解专业服务 ↗':info.tab==='bundles'?'查看权益包 ↗':'查看单次服务 ↗'));box.append(card)}
 const slides=[...box.children],controls=node('div',undefined,'home-carousel-controls'),previous=node('button','←','home-carousel-arrow'),dots=node('div',undefined,'home-carousel-dots'),next=node('button','→','home-carousel-arrow');previous.type=next.type='button';previous.setAttribute('aria-label','上一项服务');next.setAttribute('aria-label','下一项服务');
 const dotButtons=slides.map((slide,index)=>{const dot=node('button',undefined,'home-carousel-dot');dot.type='button';dot.setAttribute('aria-label','查看'+slide.querySelector('b').textContent);dot.onclick=()=>show(index);dots.append(dot);return dot});controls.append(previous,dots,next);box.after(controls);
 let current=0,timer,scrollTimer;const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 function mark(index){current=(index+slides.length)%slides.length;slides.forEach((slide,i)=>slide.setAttribute('aria-current',String(i===current)));dotButtons.forEach((dot,i)=>dot.setAttribute('aria-current',String(i===current)))}
 function slideLeft(slide){return slide.offsetLeft-slides[0].offsetLeft}function show(index,behavior='smooth'){mark(index);box.scrollTo({left:slideLeft(slides[current]),behavior:reduced?'auto':behavior})}
 function stop(){clearInterval(timer)}function start(){stop();if(!reduced&&!document.hidden)timer=setInterval(()=>show(current+1),4800)}
 previous.onclick=()=>{show(current-1);start()};next.onclick=()=>{show(current+1);start()};box.addEventListener('scroll',()=>{clearTimeout(scrollTimer);scrollTimer=setTimeout(()=>{const nearest=slides.reduce((best,slide,index)=>Math.abs(slideLeft(slide)-box.scrollLeft)<best.distance?{index,distance:Math.abs(slideLeft(slide)-box.scrollLeft)}:best,{index:0,distance:Infinity});mark(nearest.index)},90)},{passive:true});box.addEventListener('pointerenter',stop);box.addEventListener('pointerleave',start);box.addEventListener('touchstart',stop,{passive:true});box.addEventListener('touchend',start,{passive:true});controls.addEventListener('focusin',stop);controls.addEventListener('focusout',start);document.addEventListener('visibilitychange',()=>document.hidden?stop():start());mark(0);start();
}
function selectServiceTab(tab){
 if(!['single','bundles','professional'].includes(tab))tab='single';
 document.querySelectorAll('#pricing [role="tab"]').forEach(button=>button.setAttribute('aria-selected',String(button.dataset.serviceTab===tab)));
 document.querySelectorAll('#pricing [data-service-panel]').forEach(panel=>panel.hidden=panel.dataset.servicePanel!==tab);
}
renderSingleProducts();renderBundles();renderProfessional();renderHomeServices();
document.addEventListener('click',event=>{const target=event.target.closest('[data-service-tab]');if(target)selectServiceTab(target.dataset.serviceTab)});
async function openPricingProduct(p){
 if(p.fen===0){location.hash='profile';go('profile');return}
 if(p.id==='rectification'){await window.rectificationReady;location.hash='rectification-product';go('rectification-product');return window.openRectificationProduct()}
 if(loggedIn){
  const rights=await refreshEntitlements();
  if(['single','topic','consult'].includes(p.id)&&await resumeActiveService(p.id))return;
  if(['single','topic','consult'].includes(p.id)&&(rights[p.id]||0)>0){
   await openEntitledService(p.id);return;
  }
  if(p.id==='annual'&&(rights['annual:any']||0)>0){location.hash='reading';go('reading');toast('年度权益已到账，请选择年份后直接生成');return}
 }
 upgradeSource='';checkoutProductId=p.id;updateCheckout();location.hash='payment';go('payment');
}
document.addEventListener('click',event=>{const target=event.target.closest('[data-checkout-product]');if(!target)return;const id=target.dataset.checkoutProduct;if(products.some(product=>product.id===id)){upgradeSource='';checkoutProductId=id;updateCheckout()}},true);
document.querySelectorAll('input[name="payment-method"]').forEach(input=>input.addEventListener('change',updateCheckout));
$('#payment-preview').onclick=()=>busy($('#payment-preview'),async()=>{
 const p=selectedProduct();
 const channel=selectedPayment();if(!paymentCapability.paymentChannels?.[channel])throw Error(paymentNames[channel]+'尚未开放，请选择已启用的支付方式');
 if(!paymentCapability.payableProducts?.includes(p.id))throw Error('该服务仍在完善交付流程，暂未开放付款');
 if(!paymentCapability.paymentReady)throw Error('支付服务尚未完成服务器配置');
 if(!requireAccountView('payment'))return;
 const body={product:p.id,channel};if(p.id==='annual')body.year=annualPurchaseYear;
 if(channel==='wechat'&&!/android|iphone|ipod|ipad|mobile|windows phone/i.test(navigator.userAgent)){
  $('#payment-status').textContent='正在生成微信支付二维码…';
  const order=await api('payment/orders',body);
  showWechatNative(order);
  return;
 }
 $('#payment-status').textContent='正在前往主域名安全支付中心…';
 const handoff=await api('payment/handoff',body);
 location.href=handoff.checkoutUrl;
});

let nativeTimer=null;
function showWechatNative(order){
 let dialog=$('#wechat-native-dialog');
 if(!dialog){
  dialog=document.createElement('dialog');dialog.id='wechat-native-dialog';dialog.className='completion-dialog';
  dialog.innerHTML='<span class="badge">微信 Native 支付</span><h2>请使用微信扫码支付</h2><img id="wechat-native-qr" alt="微信支付二维码" style="display:block;width:min(280px,80vw);margin:18px auto;padding:14px;box-sizing:border-box;border-radius:16px;background:#fff"><p id="wechat-native-status" class="hint">支付成功后将自动关闭并解锁服务。</p><button id="wechat-native-cancel" class="text-button" type="button">暂不支付</button>';
  document.body.append(dialog);$('#wechat-native-cancel').onclick=()=>{clearTimeout(nativeTimer);dialog.close()};
 }
 $('#wechat-native-qr').src='/api/payment/orders/'+encodeURIComponent(order.id)+'/wechat-qr';
 $('#wechat-native-status').textContent='支付成功后将自动关闭并解锁服务。';dialog.showModal();
 let attempts=0;
 const poll=async()=>{
  if(!dialog.open)return;
  try{
   const current=await api('payment/orders/'+encodeURIComponent(order.id));
   if(current.status==='paid'){
    dialog.close();$('#payment-status').textContent='支付成功，服务已解锁并保存到当前账号。';
    await refreshEntitlements();showPaymentUnlock(current);return;
   }
  }catch(error){console.warn('native payment status check failed',error)}
  if(++attempts<200)nativeTimer=setTimeout(poll,3000);
 };
 poll();
}
function previewUpgrade(from,to){
 const source=products.find(p=>p.id===from),target=products.find(p=>p.id===to);
 if(!source||!target||source.fen>=target.fen)return;
 upgradeSource=from;checkoutProductId=to;updateCheckout();location.hash='payment';go('payment');
}
$('#checkout-experience').onclick=()=>openExperience(selectedProduct().id);
updateCheckout();
api('status').then(value=>{paymentCapability=value;const selected=document.querySelector('input[name="payment-method"]:checked');if(!value.paymentChannels?.[selected?.value]){const ready=document.querySelector('input[name="payment-method"][value="wechat"]');if(value.paymentChannels?.wechat&&ready)ready.checked=true}updateCheckout();checkReturnedPayment();checkRecentPaidUnlock()}).catch(()=>{});
const readingBanner=document.querySelector('#reading .paid-services-banner small');if(readingBanner)readingBanner.textContent='付费服务由服务器核验订单，支付成功后自动保存到登录账号。';
const differenceUpgradeBox=document.querySelector('#pricing > .upgrade-explainer');if(differenceUpgradeBox)differenceUpgradeBox.remove();
const annualCard=[...document.querySelectorAll('#reading .card')].find(card=>card.querySelector('#annual-ai'));if(annualCard){const heading=annualCard.querySelector('h2');if(heading)heading.textContent='印占年运报告';const badge=annualCard.querySelector('.badge');if(badge)badge.textContent='¥2.9 / 所选年度 · AI 生成';const hint=annualCard.querySelector('h2 + .hint');if(hint)hint.textContent='以大运和小运判断未来三年的阶段变化，重点分析所选年度的事业、财富、爱情、婚姻与健康，并结合年度返照、三级运和行运判断年度趋势。';const consent=annualCard.querySelector('#annual-consent + span');if(consent)consent.textContent='同意将本命盘、核心分盘、大小运、年度返照、行运及八分盘等派生数据发送至AI，生成所选年度报告。内容仅供文化学习与自我探索。';if(hint&&!annualCard.querySelector('.annual-content-list')){const title=node('strong','包含内容');const list=node('ul','');list.className='annual-content-list';for(const item of ['未来三年小运阶段与转折','所选年度五大领域预测','年度主要趋势与现实转折','关键机会、风险与行动建议'])list.append(node('li',item));const note=node('p','以小运梳理未来三年的发展节奏，再通过年度返照、三级运与行运，分析所选年度可能出现的重要变化。');note.className='hint';hint.after(title,list,note)}const mainButton=annualCard.querySelector('#annual-ai');if(mainButton)mainButton.textContent='查看印占年运报告 · ¥2.9 ↗';const detailButton=annualCard.querySelector('#annual');if(detailButton)detailButton.textContent='查看印占年运报告 · ¥2.9';const summary=annualCard.querySelector('details summary');if(summary)summary.textContent='印占年运报告价格与基础说明'}
const serviceBanner=document.querySelector('#reading .paid-services-banner p');if(serviceBanner)serviceBanner.textContent='印占年运报告 ¥2.9 · 单项 ¥4.9 · 专题 ¥19.9 · 全盘咨询 ¥29.9';
const natalUpgrade=document.querySelector('#natal-upgrade p');if(natalUpgrade)natalUpgrade.textContent='¥2.9 看印占年运报告，¥4.9 起深入一个具体问题。';
const checkoutNotice=document.querySelector('.checkout-notice p');if(checkoutNotice)checkoutNotice.firstChild.textContent='支付宝、微信支付和 PayPal 均由服务器核验并自动发放权益；PayPal按美元收费。';
const pricingFootnote=document.querySelector('.pricing-footnote');if(pricingFootnote)pricingFootnote.textContent='价格与权益数量由服务器校验；权益有效期遵循后台商品配置，结账页与到账记录为准。';

let unlockedOrder=null,paymentReturnChecking=false,recentUnlockChecking=false;
const unlockDialog=$('#payment-unlock-dialog');
const unlockSeenKey='xingxu-payment-unlock-seen';
const unlockDetails={
 annual:{title:'印占年运报告已解锁',copy:'所选年度的AI报告权益已经到账。',benefits:['1份所选年度深度报告','未来三年阶段脉络','五大生活领域分析','年度机会、风险与行动建议','已生成报告可重复查看']},
 single:{title:'AI单项解读已解锁',copy:'围绕一个具体问题的单项解读已经到账。',benefits:['1张指定图谱','简洁报告＋2轮追问']},
 topic:{title:'多盘专题分析已解锁',copy:'你的定制研究权益已经到账。',benefits:['自选2–5张图谱','深度报告＋5轮追问']},
 consult:{title:'连续AI咨询已解锁',copy:'你的连续咨询空间已经开启。',benefits:['自选1–5张分盘 · 微运年运固定启用','30轮连续AI咨询']},
 explorer_starter:{title:'探索体验包权益已到账',copy:'年度趋势报告、单项聚焦解读与本命报告延伸问答已分别进入你的探索权益。',benefits:['年度趋势报告 1份','单项聚焦解读 1份','本命报告延伸问答 3轮']},
 explorer_deep:{title:'深度探索包权益已到账',copy:'5份独立解读权益已发放，可分开使用并与原余额累计。',benefits:['年度趋势报告 1份','单项聚焦解读 3份','多维综合解读 1份']},
 rectification:{title:'出生时间校准已解锁',copy:'服务已保存到当前账号，可现在开始或稍后继续。',benefits:['六阶段资料采集','草稿跨设备恢复','专业校准报告']}
};
function showPaymentUnlock(order){
 unlockedOrder=order;const detail=unlockDetails[order.product]||{title:'服务已经解锁',copy:'本次服务已保存到你的登录账号。',benefits:['账号权益已到账']};
 $('#payment-unlock-title').textContent=detail.title;$('#payment-unlock-copy').textContent=detail.copy;
 const benefits=$('#payment-unlock-benefits');benefits.replaceChildren();for(const line of detail.benefits)benefits.append(node('span',line));
 $('#payment-unlock-enter').textContent=order.product==='annual'?'立即生成报告 ↗':'立即进入服务 ↗';
 if(order.id){const seen=JSON.parse(localStorage.getItem(unlockSeenKey)||'[]');if(!seen.includes(order.id))localStorage.setItem(unlockSeenKey,JSON.stringify([order.id,...seen].slice(0,60)))}
 if(!unlockDialog.open)unlockDialog.showModal();
}
$('#payment-unlock-later').onclick=()=>unlockDialog.close();
$('#payment-unlock-enter').onclick=e=>busy(e.currentTarget,async()=>{
 const order=unlockedOrder;if(!order)return;unlockDialog.close();
 if(order.product==='annual'){
  const paidYear=Number(order.productRef)||new Date().getFullYear();annualPurchaseYear=paidYear;if(yearField)yearField.value=String(paidYear);
  location.hash='reading';go('reading');setTimeout(()=>$('#annual-ai')?.scrollIntoView({behavior:'smooth',block:'center'}),100);toast(paidYear+'年报告权益已到账，可以直接生成');return;
 }
 if(['explorer_starter','explorer_deep'].includes(order.product)){location.hash='mine';go('mine');await refreshEntitlements();toast('套餐权益已独立到账，可从“我的探索权益”使用');return}
 if(order.product==='rectification'){await window.rectificationReady;return window.showRectificationPreview(order.id)}
 await openEntitledService(order.product);
});
async function checkReturnedPayment(attempt=0){
 const query=new URLSearchParams(location.search),orderId=query.get('payment_order')||sessionStorage.getItem('xingxu-payment-order');
 if(!orderId||paymentReturnChecking&&attempt===0)return;if(!loggedIn){setTimeout(()=>checkReturnedPayment(attempt),800);return}
 paymentReturnChecking=true;
 try{
  const order=await api('payment/orders/'+encodeURIComponent(orderId));
  if(order.status==='paid'){
   sessionStorage.removeItem('xingxu-payment-order');window.history.replaceState(null,'',location.pathname+'#payment');
   $('#payment-status').textContent='支付成功，服务已解锁并保存到当前账号。';await refreshEntitlements();showPaymentUnlock(order);paymentReturnChecking=false;
  }else if(attempt<12){$('#payment-status').textContent='付款已返回，正在确认权益到账…';setTimeout(()=>{paymentReturnChecking=false;checkReturnedPayment(attempt+1)},2000)}
  else{$('#payment-status').textContent='付款确认稍有延迟。权益到账后会保存在账号，可稍后在“我的”查看。';paymentReturnChecking=false}
 }catch(e){$('#payment-status').textContent=e.message;paymentReturnChecking=false}
}

async function checkRecentPaidUnlock(attempt=0){
 if(recentUnlockChecking||unlockDialog.open)return;
 if(!accessReady||!loggedIn){if(attempt<40)setTimeout(()=>checkRecentPaidUnlock(attempt+1),500);return}
 recentUnlockChecking=true;
 try{
  const result=await api('account/orders'),seen=JSON.parse(localStorage.getItem(unlockSeenKey)||'[]'),now=Date.now()/1000;
  const order=(result.items||[]).find(item=>item.status==='paid'&&item.paidAt&&now-item.paidAt<86400&&!seen.includes(item.id));
  if(order){location.hash='payment';go('payment');$('#payment-status').textContent='支付成功，服务已解锁并保存到当前账号。';await refreshEntitlements();showPaymentUnlock(order)}
 }catch(e){console.warn('recent payment unlock check failed',e)}finally{recentUnlockChecking=false}
}

// 本地视觉验收入口，不创建订单，也不发放权益。
if(['127.0.0.1','localhost'].includes(location.hostname)){
 const preview=new URLSearchParams(location.search).get('payment_unlock_preview');
 if(unlockDetails[preview])setTimeout(()=>showPaymentUnlock({id:'',product:preview,productRef:preview==='annual'?String(new Date().getFullYear()):''}),300);
}

function openPaidProduct(id){
 upgradeSource='';checkoutProductId=id;updateCheckout();location.hash='payment';go('payment');
}
window.openRectificationCheckout=()=>openPaidProduct('rectification');
async function openAnnualOffer(){
 const currentYear=new Date().getFullYear(),year=annualManualYear?Number(yearField?.value)||currentYear:currentYear;
 const yearInput=$('#year');if(yearInput)yearInput.value=String(year);
 annualPurchaseYear=year;
 if(!requireAccountView('reading'))return;
 const rights=await refreshEntitlements();
 if((rights?.['annual:'+year]||0)+(rights?.['annual:any']||0)>0){
  if(!$('#annual-consent').checked){toast('请先勾选年度解读的数据处理说明');return}
  await generateReading('annual');return
 }
 openPaidProduct('annual');
 $('#checkout-description').textContent=year+'年 · '+selectedProduct().description;
}
