"use strict";
const order=document.body.dataset.order;
const back=document.body.dataset.back;
let tries=0;
async function poll(){
 try{
  const response=await fetch('/api/payment/wechat/native-status/'+encodeURIComponent(order),{cache:'no-store'});
  const result=await response.json();
  if(result.status==='paid'){
   document.querySelector('#status').textContent='支付成功，正在解锁服务…';
   location.replace(back);
   return;
  }
 }catch(error){console.warn('payment status check failed',error)}
 if(++tries<300)setTimeout(poll,2000);
}
poll();
