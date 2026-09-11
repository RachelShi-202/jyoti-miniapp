const KEY='jyoti-session-v3';
const empty=()=>({session:null,member:false,profile:null,chart:null,draft:{date:'',time:'',accuracy:0,region:[],placeLabel:'',placeToken:'',fold:null,consent:false},saved:false,notes:{}});
function validate(d){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(d.date))return '请选择出生日期';
 const p=d.date.split('-').map(Number),dt=new Date(p[0],p[1]-1,p[2]);
 if(dt.getFullYear()!==p[0]||dt.getMonth()!==p[1]-1||dt.getDate()!==p[2]||dt>new Date()||p[0]<1900)return '请选择有效出生日期';
 if(!/^([01]\d|2[0-3]):[0-5]\d$/.test(d.time))return '请选择出生时刻';
 if(!d.placeToken)return '请先匹配并确认出生地点';
 if(!d.consent)return '请先同意资料处理说明';return '';
}
function canRead(s){return !!(s.session&&s.session.token&&s.session.expiresAt>Date.now()/1000&&s.profile)}
module.exports={KEY,empty,validate,canRead};
