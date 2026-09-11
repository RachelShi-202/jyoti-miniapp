const store=require('./services/store');App({globalData:{mode:'service',brand:'星序.JYOTI'},onLaunch(){this.boot=store.launch().catch(e=>{this.globalData.bootError=e.message})}})
