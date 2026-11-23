import hashlib,sqlite3,time
from contextlib import contextmanager
import entitlements,payments,rectification

class Store:
    def __init__(self,path): self.path=path
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path)
        try:
            yield db
            db.commit()
        finally: db.close()

def add_code(store,code,product,expires=0):
    with store.connect() as db:
        db.execute('INSERT INTO invite_codes(digest,expires,max_uses,disabled,product) VALUES (?,?,1,0,?)',(hashlib.sha256(code.encode()).hexdigest(),expires,product))

def test_migrates_old_codes_as_topic(tmp_path):
    store=Store(tmp_path/'old.sqlite3')
    with store.connect() as db:
        db.execute('CREATE TABLE invite_codes(digest TEXT PRIMARY KEY,expires REAL NOT NULL,max_uses INTEGER NOT NULL,disabled INTEGER NOT NULL DEFAULT 0)')
        db.execute('CREATE TABLE sessions(owner_id TEXT,payload TEXT)')
        db.execute('CREATE TABLE schema_version(version INTEGER PRIMARY KEY)')
        db.execute('INSERT INTO invite_codes VALUES (?,?,1,0)',(hashlib.sha256(b'OLD-CODE').hexdigest(),time.time()+1000))
        entitlements.initialize(db)
    result=entitlements.redeem(store,'u1','old-code')
    assert result['product']=='topic'
    assert entitlements.summary(store,'u1')['topic']==1

def test_consult_and_no_expiry(tmp_path):
    store=Store(tmp_path/'new.sqlite3')
    with store.connect() as db:
        db.execute('CREATE TABLE sessions(owner_id TEXT,payload TEXT)')
        db.execute('CREATE TABLE schema_version(version INTEGER PRIMARY KEY)')
        entitlements.initialize(db)
    add_code(store,'CONSULT','consult',0)
    assert entitlements.redeem(store,'u1','consult')['product']=='consult'
    assert entitlements.summary(store,'u1')['consult']==1
    reservation=entitlements.reserve(store,'u1','consult')
    assert reservation

def test_rectification_code_creates_one_paid_test_order_and_task(tmp_path):
    store=Store(tmp_path/'rectification.sqlite3')
    with store.connect() as db:
        db.execute('CREATE TABLE sessions(owner_id TEXT,payload TEXT)')
        db.execute('CREATE TABLE schema_version(version INTEGER PRIMARY KEY)')
        entitlements.initialize(db);payments.initialize(db)
    rectification.initialize(store)
    add_code(store,'RECTIFICATION-TEST','rectification',0)
    result=entitlements.redeem(store,'tester','RECTIFICATION-TEST')
    assert result['product']=='rectification'
    first=payments.unlock_rectification_invite(store,'tester','RECTIFICATION-TEST')
    second=payments.unlock_rectification_invite(store,'tester','RECTIFICATION-TEST')
    assert first['id']==second['id'] and first['status']=='paid' and first['amountFen']==0
    task=rectification.start(store,'tester',first['id'])
    assert task['status']=='draft' and task['orderId']==first['id']

def test_single_and_no_expiry_survives_relogin_until_used(tmp_path):
    store=Store(tmp_path/'single.sqlite3')
    with store.connect() as db:
        db.execute('CREATE TABLE sessions(owner_id TEXT,payload TEXT)')
        db.execute('CREATE TABLE schema_version(version INTEGER PRIMARY KEY)')
        entitlements.initialize(db)
    add_code(store,'SINGLE-RELOGIN','single',0)
    assert entitlements.redeem(store,'account-single','single-relogin')['product']=='single'
    assert entitlements.summary(store,'account-single')['single']==1
    reopened=Store(store.path)
    assert entitlements.summary(reopened,'account-single')['single']==1
    reservation=entitlements.reserve(reopened,'account-single','single')
    assert reservation
    assert entitlements.summary(reopened,'account-single')['single']==0

def test_annual_any_can_reserve_selected_year(tmp_path):
    store=Store(tmp_path/'annual.sqlite3')
    with store.connect() as db:
        db.execute('CREATE TABLE sessions(owner_id TEXT,payload TEXT)')
        db.execute('CREATE TABLE schema_version(version INTEGER PRIMARY KEY)')
        entitlements.initialize(db)
    add_code(store,'ANNUAL','annual:any',0)
    entitlements.redeem(store,'u1','annual')
    reservation=entitlements.reserve(store,'u1','annual:2030')
    assert reservation
    assert entitlements.summary(store,'u1')['annual:any']==0
    with store.connect() as db:
        row=db.execute('SELECT product FROM credit_uses WHERE id=?',(reservation,)).fetchone()
    assert row[0]=='annual:2030'

def test_redeemed_entitlement_is_restored_after_relogin(tmp_path):
    store=Store(tmp_path/'relogin.sqlite3')
    with store.connect() as db:
        db.execute('CREATE TABLE sessions(owner_id TEXT,payload TEXT)')
        db.execute('CREATE TABLE schema_version(version INTEGER PRIMARY KEY)')
        entitlements.initialize(db)
    add_code(store,'CONSULT-RELOGIN','consult',0)
    assert entitlements.redeem(store,'account-1','CONSULT-RELOGIN')['product']=='consult'
    assert entitlements.summary(store,'account-1')['consult']==1
    # Reopening the same database is the server-side equivalent of logout,
    # container restart, and a fresh login session.
    reopened=Store(store.path)
    assert entitlements.summary(reopened,'account-1')['consult']==1
    reservation=entitlements.reserve(reopened,'account-1','consult')
    assert reservation

def test_repair_rebuilds_missing_grant_from_redemption(tmp_path):
    store=Store(tmp_path/'repair.sqlite3')
    with store.connect() as db:
        db.execute('CREATE TABLE sessions(owner_id TEXT,payload TEXT)')
        db.execute('CREATE TABLE schema_version(version INTEGER PRIMARY KEY)')
        entitlements.initialize(db)
    add_code(store,'BROKEN-REDEMPTION','consult',0)
    digest=hashlib.sha256(b'BROKEN-REDEMPTION').hexdigest()
    with store.connect() as db:
        db.execute('INSERT INTO invite_redemptions VALUES (?,?,?)',(digest,'account-2',time.time()))
    assert entitlements.summary(store,'account-2')['consult']==1
