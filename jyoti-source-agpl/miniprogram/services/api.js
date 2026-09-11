const config=require('../config');
let initialized=false;
function initCloud(){
 if(initialized)return;
 if(!wx.cloud||typeof wx.cloud.callContainer!=='function')throw new Error('当前微信版本不支持云托管，请升级微信后重试');
 if(!config.cloudEnv||!config.cloudService)throw new Error('云托管环境尚未配置');
 wx.cloud.init({env:config.cloudEnv,traceUser:false});initialized=true;
}
async function request(path,method='GET',data,token){
 initCloud();
 let r;
 try{r=await wx.cloud.callContainer({config:{env:config.cloudEnv},path,method,data,timeout:60000,header:{'Content-Type':'application/json','X-WX-SERVICE':config.cloudService,Authorization:token?'Bearer '+token:''}})}
 catch(e){const err=new Error('无法连接云端服务，请检查云托管状态及小程序关联权限'+(e.errCode?'（'+e.errCode+'）':''));throw err}
 let body=r.data;
 if(typeof body==='string'){try{body=JSON.parse(body)}catch(_){body=null}}
 if(r.statusCode>=200&&r.statusCode<300){if(body===null||body===undefined)throw new Error('云端返回内容异常，请稍后重试');return body}
 const err=new Error(body&&typeof body.detail==='string'?body.detail:'云端服务暂不可用（HTTP '+r.statusCode+'）');err.status=r.statusCode;throw err;
}
function login(){
 if(config.localDeveloperLogin){if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(config.apiBase))return Promise.reject(new Error('开发登录只支持本机地址'));return request('/v1/auth/local','POST',{})}
 return new Promise((resolve,reject)=>wx.login({timeout:10000,success:r=>r.code?resolve(r.code):reject(new Error('微信登录未返回有效凭证')),fail:()=>reject(new Error('微信登录失败，请重试'))})).then(code=>request('/v1/auth/wechat','POST',{code}));
}
module.exports={request,login,initCloud};
