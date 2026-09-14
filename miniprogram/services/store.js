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
 // No login prompt or guest network request on first entry.
 // A guest session is created only when a query actually needs the backend.
}
async function signIn(){
 const session=await api.login();
 const result=await api.request('/v1/me','GET',undefined,session.token);
 epoch++;state.session=session;state.member=result.member;wx.setStorageSync(SESSION,session);
 // Keep the visible guest chart and draft; server-side place tokens must be renewed.
 patchDraft({placeToken:''});return state;
}
async function requireMember(){
 if(state.member&&state.session&&state.session.expiresAt>Date.now()/1000)return true;
 const agree=await new Promise(resolve=>wx.showModal({title:'登录后使用查询记录',content:'微信登录用于保存和查看查询记录。取消后仍可浏览、排盘和查看本次结果，不需要授权手机号。',confirmText:'微信登录',cancelText:'暂不登录',success:r=>resolve(r.confirm),fail:()=>resolve(false)}));
 if(!agree)return false;
 await signIn();return true;
}
async function saveChart(){
 const profile=state.profile;
 if(!profile)throw new Error('请先完成本次星盘查询');
 const wasMember=state.member;
 if(!await requireMember())return false;
 if(!wasMember){
  const place=await resolvePlace(profile.placeLabel);
  const result=await authenticated('/v1/profile','PUT',{date:profile.date,time:profile.time,fold:profile.fold,placeToken:place.placeToken,consent:true});
  state.profile=result.profile;state.chart=result.chart;patchDraft(place);
 }
 await authenticated('/v1/history','POST',{});return true;
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
module.exports={read,write,patchDraft,launch,signIn,requireMember,saveChart,resolvePlace,saveProfile,logout,remove,clearLocal,track,canRead,getReport,authenticated,birth};
