# 0.4.0 会员数据与版本发布

## 当前交付状态

已实现 MySQL 存储适配；会员、登录凭证散列、历史记录与活跃统计通过统一事务层存取。
SQLite 仅保留用于本地开发和旧数据迁移。没有创建数据库或迁移任何线上数据。
本地测试覆盖 SQLite 跨进程读取、事务回滚、权限隔离、账户删除与 AI 保存竞争、迁移只读预览。
MySQL 未在真实实例上联调，必须在云端完成以下验收后才能称为持久化已启用。

## 创建及配置

使用云托管可访问的 MySQL，建议通过内网连接，不要开放数据库给所有公网地址。
云开发 MySQL 可能需要在云托管开启匹配的私有网络配置。以控制台实际提供的地址为准。
官方说明：https://docs.cloudbase.net/run/develop/resource-integration/mysql
直连说明：https://docs.cloudbase.net/database/configuration/db/tdsql/direct-connection
数据库可能产生费用，需由账户所有者确认并创建。

云端环境变量（保留原有微信、地图、AI 配置）：

```
JYOTI_STORAGE=mysql
MYSQL_HOST=数据库内网主机名
MYSQL_PORT=3306
MYSQL_DATABASE=jyoti
MYSQL_USER=专用数据库账户
MYSQL_PASSWORD=仅在云端填写的密码
```

使用独立数据库；部署账号需要创建应用表及读写这些表的权限。MySQL 表使用 InnoDB、utf8mb4_bin。
使用外部网络时须配置 MYSQL_SSL_CA 指向可信 CA 文件；代码会同时校验证书与主机名。
CA 文件如需随镜像提供，应自行加入 Dockerfile；本包不包含私有证书和密钥。
程序不会在 MySQL 连接失败时回退到 SQLite，避免会员记录分散到临时文件。

## 已有会员数据：必须先保全

不要为了迁移先重建旧容器。若旧容器已有需要保留的记录，请先停止写入并导出 SQLite 的一致性副本，
或由腾讯云支持协助备份；数据库通常位于 /app/data/jyoti.sqlite3，以原 JYOTI_DB 设置为准。
普通本机文件不能代替线上数据库副本。已被容器销毁的记录无法由本工具恢复。

在受控环境配置上述 MySQL 环境变量后执行：

```
python backend/migrate_members.py /安全位置/线上数据库副本.sqlite3
python backend/migrate_members.py /安全位置/线上数据库副本.sqlite3 --apply
```

第一条仅读取来源并显示各表数量；第二条只允许目标表为空，整批在事务中导入并核对行数。
工具不会删除来源或覆盖已有目标记录。迁移期间暂停旧服务写入，切换新版本后不要再切回旧 SQLite 版本。
没有旧数据需要保留时可以跳过导入；不能未经确认假定线上没有记录。
平台数据库备份应另外配置；本程序不负责自动备份。备份包含用户资料，不可放进 GitHub。

## 部署与验收

1. GitHub Desktop 推送同一仓库的所有待推送提交。
2. 用 tools/package_backend.py 生成后端包；上传 ZIP，目录 .，端口 8000，Dockerfile。
3. GET /health 应显示 release=0.4.0、storageBackend=mysql、memberStoragePersistent=true。
   此状态确认使用 MySQL 驱动，不等于已经验证备份或云数据库高可用。
4. 会员登录并生成记录，退出、重新进入后从历史打开。另一个会员必须无法读取它。
5. 重启云端实例后重新登录，确认同一记录仍在；删除账户资料后确认历史不可再读取。
6. 桌面前端的“资料与 AI 说明”应显示 0.4.0；源码链接应为正式 GitHub 地址。

当前游客会话、当前排盘、地点确认、AI 任务和限流仍是进程内存。因此本版本先限定单实例、单工作进程，
不进行跨实例流量分配；若暂时关闭缩容至零、保留一个实例，会增加持续运行费用。
重启期间正在进行的临时查询和 AI 任务仍可能失效，需要重试；已写入 MySQL 的会员历史不随容器删除。
这不是完整多实例改造，也不代表已经满足微信业务审核要求。

## 统一版本来源

只编辑根目录 release.json，然后运行 python3 tools/sync_release.py。
打包前会检查前后端生成文件是否匹配；不一致则停止打包。
同步后的桌面工程可以继续在微信开发者工具使用，GitHub Desktop 使用 work/github-jyoti-audit 仓库推送。
后续改动请先在仓库完成，再同步到桌面，避免两个目录独立演化。
