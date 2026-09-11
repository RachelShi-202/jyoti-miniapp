const release=require('../../release-config');Page({data:{sourceUrl:release.sourceUrl||''},copySource(){if(this.data.sourceUrl)wx.setClipboardData({data:this.data.sourceUrl})}})
