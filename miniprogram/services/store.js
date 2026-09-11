const {empty,validate,canRead}=require('./domain');const api=require('./api');
const SESSION='jyoti-session-v3';let state=empty();let epoch=0;
function read(){return state}
function write(s){state=s;return s}
function patchDraft(d){state.draft=Object.assign({},state.draft,d)}
function track(){}
async function authenticated(path,method='GET',data){
 const s=state,version=epoch;if(!s.session||s.session.expiresAt<=Date.now()/1000)throw new Error('请返回首页重新登录');
 try{const result=await api.request(path,method,data,s.session.token);if(version!==epoch)throw new Error('本次查询已结束');return result}catch(e){if(e.status===401&&version===epoch){state.session=null;wx.removeStorageSync(SESSION)}throw e}
}
async function launch(){
 epoch++;state=empty();state.session=wx.getStorageSync(SESSION)||null;
 // Remove old versions' persistent birth information; only auth token survives v3 launches.
 ['jyoti-service-v2','jyoti-demo-v1'].forEach(k=>wx.removeStorageSync(k));
 if(state.session&&state.session.guest)state.session=null;
 if(state.session){try{const result=await authenticated('/v1/session/reset','POST',{});state.member=result.member}catch(e){state.session=null;wx.removeStorageSync(SESSION)}}
 if(!state.member){const agree=await new Promise(resolve=>wx.showModal({title:'欢迎来到星序',content:'微信登录成为免费会员，系统将自动保存你的星盘及解析，便于再次查看。使用微信身份标识关联账户，不读取个人微信号。你也可以选择游客体验，不保存查询历史。',confirmText:'微信登录',cancelText:'游客体验',success:r=>resolve(r.confirm),fail:()=>resolve(false)}));if(agree){try{await signIn()}catch(e){wx.showModal({title:'微信登录未完成',content:e.message||'请稍后重试',showCancel:false,confirmText:'知道了'});await guest()}}else await guest()}
}
async function signIn(){
 if(state.session&&!state.session.guest&&state.member&&state.session.expiresAt>Date.now()/1000){const result=await authenticated('/v1/me');state.member=result.member;return state}
 const session=await api.login();epoch++;state.profile=null;state.chart=null;patchDraft({placeToken:'',placeLabel:''});state.session=session;wx.setStorageSync(SESSION,session);const result=await authenticated('/v1/me');state.member=result.member;return state;
}
async function guest(){state.session=await api.request('/v1/auth/guest','POST',{});state.member=false;wx.removeStorageSync(SESSION);return state}
async function ensureSession(){if(!state.session||state.session.expiresAt<=Date.now()/1000)await guest()}
async function resolvePlace(address){await ensureSession();return authenticated('/v1/places/resolve','POST',{address})}
function birth(d){return {date:d.date,time:d.time,placeToken:d.placeToken,fold:d.fold,consent:true}}
async function saveProfile(){const d=state.draft,error=validate(d);if(error)throw new Error(error);await ensureSession();const result=await authenticated('/v1/profile','PUT',birth(d));state.profile=result.profile;state.chart=result.chart;state.member=result.member;return state}
async function logout(){if(state.session)await authenticated('/v1/auth/logout','POST',{});clearLocal()}
async function remove(){if(state.session)await authenticated('/v1/account/data','DELETE');clearLocal()}
function clearLocal(){epoch++;state=empty();wx.removeStorageSync(SESSION)}
async function getReport(period){if(!canRead(state))throw new Error('请先完成本次星盘查询');return authenticated('/v1/reports/'+encodeURIComponent(period))}
module.exports={read,write,patchDraft,launch,signIn,resolvePlace,saveProfile,logout,remove,clearLocal,track,canRead,getReport,authenticated,birth};
