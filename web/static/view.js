'use strict';
(()=>{
 const query=new URLSearchParams(location.search);
 if(query.has('payment_order')){
  location.replace('/mobile'+location.search+'#payment');
  return;
 }
 const mobile=document.querySelector('.choice.mobile');
 if(mobile&&location.hash==='#payment')mobile.href='/mobile#payment';
})();
