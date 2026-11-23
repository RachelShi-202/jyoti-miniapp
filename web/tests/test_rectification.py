import sqlite3
import pytest
from fastapi import HTTPException
import payments,rectification

class Store:
 def __init__(self,path):
  self.path=path
  with self.connect() as db:
   db.execute('CREATE TABLE schema_version(version INTEGER PRIMARY KEY)')
   payments.initialize(db)
  rectification.initialize(self)
 def connect(self):return sqlite3.connect(self.path)

def paid_order(store,owner):
 order=payments.create_local(store,owner,'rectification')
 with store.connect() as db:db.execute("UPDATE payment_orders SET status='paid',paid_at=1 WHERE id=?",(order['id'],))
 return order

def test_price_and_paid_order_create_owner_isolated_task(tmp_path):
 store=Store(tmp_path/'r.sqlite3');order=paid_order(store,'owner-a')
 assert order['amountFen']==3990
 task=rectification.start(store,'owner-a',order['id'])
 assert task['status']=='draft' and task['orderId']==order['id']
 assert rectification.current(store,'owner-b')['task'] is None
 with pytest.raises(HTTPException):rectification.start(store,'owner-b',order['id'])

def test_privacy_draft_resume_and_submit_state(tmp_path):
 store=Store(tmp_path/'r.sqlite3');order=paid_order(store,'owner');task=rectification.start(store,'owner',order['id'])
 with pytest.raises(HTTPException):rectification.save_draft(store,'owner',task['id'],1,{'stage1':{'birthDate':'2000-01-01'}})
 rectification.accept_privacy(store,'owner',task['id'],True)
 data={
  'stage1':{'birthDate':'2000-01-01','birthPlace':'上海','knownTime':'上午','timeSource':'家人回忆','errorRange':'1小时'},
  'stage2':{'bodyBuild':'中等','facialFeatures':'描述','physicalMarks':'无'},
  'stage3':{'personality':'描述','familyBackground':'描述','migration':'描述'},
  'stage4':{'skipRelationship':True},
  'stage5':{'events':[{'category':'学业','month':'2018-09','description':'入学','impact':'重要'},{'category':'事业','month':'2022-07','description':'工作','impact':'重大'},{'category':'家庭','month':'2024-01','description':'迁居','impact':'重要'}]},
  'stage6':{'additionalNotes':''}}
 saved=rectification.save_draft(store,'owner',task['id'],6,data)
 assert saved['saved'] and saved['revision']>=2
 restored=rectification.current(store,'owner')['task']
 assert restored['draft']['stage5']['events'][1]['category']=='事业'
 assert restored['revision']>=2 and restored['currentStage']==6 and restored['lastSavedAt']>=saved['savedAt']
 result=rectification.submit(store,'owner',task['id'])
 assert result['status']=='submitted' and result['progress']==100
 assert rectification.current(store,'owner')['task']['deletionStatus']=='retained'

def test_schema_exposes_guarded_automatic_deletion(tmp_path):
 store=Store(tmp_path/'r.sqlite3')
 info=rectification.schema_info()
 assert info['automaticDeletionEnabled'] is True
 assert set(info['statuses'])=={'draft','submitted','processing','completed','failed','expired'}

def test_report_is_saved_before_private_draft_is_deleted(tmp_path):
 store=Store(tmp_path/'r.sqlite3');order=paid_order(store,'owner');task=rectification.start(store,'owner',order['id'])
 rectification.accept_privacy(store,'owner',task['id'],True)
 data={
  'stage1':{'birthDate':'2000-01-01','birthPlace':'上海','knownTime':'09:00','timeSource':'家人回忆','errorRange':'30分钟'},
  'stage2':{'bodyBuild':'中等','facialFeatures':'描述','physicalMarks':'无'},
  'stage3':{'personality':'描述','familyBackground':'描述','migration':'描述'},
  'stage4':{'skipRelationship':True},
  'stage5':{'events':[{'category':'学业','month':'2018-09','description':'入学','impact':'重要'},{'category':'事业','month':'2022-07','description':'工作','impact':'重大'},{'category':'家庭','month':'2024-01','description':'迁居','impact':'重要'}]},
  'stage6':{}}
 rectification.save_draft(store,'owner',task['id'],6,data);rectification.submit(store,'owner',task['id'])
 run=rectification.claim(store,task['id'],'policy-reviewed')
 result={'report':'报告正文','intervalStart':'08:55','intervalEnd':'09:05','referenceTime':'09:00','supportLevel':'中','limitations':'有限','d1':{'ascendant':{'sign':'白羊'}},'d9':{'ascendant':{'sign':'天秤'}}}
 assert rectification.complete(store,task['id'],run['runId'],result,'prompt-v1')
 assert rectification.report(store,'owner',task['id'])['text']=='报告正文'
 assert rectification.delete_private_data(store,task['id'])
 state=rectification.current(store,'owner')['task']
 assert state['status']=='completed' and state['deletionStatus']=='deleted' and state['draft']=={}

def test_failed_generation_keeps_draft_and_retry_does_not_need_new_order(tmp_path):
 store=Store(tmp_path/'r.sqlite3');order=paid_order(store,'owner');task=rectification.start(store,'owner',order['id'])
 rectification.accept_privacy(store,'owner',task['id'],True)
 data={'stage1':{'birthDate':'2000-01-01','birthPlace':'上海','knownTime':'09:00','timeSource':'家人回忆','errorRange':'30分钟'},'stage2':{'bodyBuild':'中等','facialFeatures':'描述','physicalMarks':'无'},'stage3':{'personality':'描述','familyBackground':'描述','migration':'描述'},'stage4':{'skipRelationship':True},'stage5':{'events':[{'category':'学业','month':'2018-09','description':'入学','impact':'重要'},{'category':'事业','month':'2022-07','description':'工作','impact':'重大'},{'category':'家庭','month':'2024-01','description':'迁居','impact':'重要'}]},'stage6':{}}
 rectification.save_draft(store,'owner',task['id'],6,data);rectification.submit(store,'owner',task['id'])
 run=rectification.claim(store,task['id'],'policy-reviewed');rectification.fail(store,task['id'],run['runId'],'MODEL_FAILED')
 assert rectification.current(store,'owner')['task']['draft']['stage1']['birthDate']=='2000-01-01'
 assert rectification.retry(store,'owner',task['id'])['status']=='submitted'
