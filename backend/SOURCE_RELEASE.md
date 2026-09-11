# 源码许可与发布说明

星序.JYOTI 原创程序代码采用 GNU AGPL v3 或更新版本；许可证原文见 LICENSE。
修改、再分发及通过网络提供修改版服务时，应遵守许可的适用义务。
本说明不是商业授权合同，也不表示 Astrodienst 对本项目背书。

## 当前状态

源码仓库：https://github.com/RachelShi-202/jyoti-miniapp
每次部署请记录对应 Git 提交号，并确保该版本源码可公开访问。
本项目明确选择 AGPL-3.0-or-later，运行不需要商业授权密钥；公开源码及保留声明的义务仍适用。
当前云端版本可能与本源码存在差异，应发布包含本次修改的后端版本后再关联对应源码版本。

## 构建与运行

1. 前端用微信开发者工具打开根目录 project.config.json。请使用自己的 AppID。
2. 在 miniprogram/release-config.js 中填入自己的云托管环境和服务名。
3. 后端使用 Python 3.12，安装 backend/requirements.txt；源码分发包附带当前 pyswisseph 上游源码。
4. 容器构建：docker build -t jyoti-api ./backend 。容器监听 8000 端口。
5. 用平台环境变量配置 WX_APP_ID、WX_APP_SECRET、TENCENT_MAP_KEY、AI_API_KEY、AI_MODEL。
   不要将真实密钥写入源码、镜像或提交至公开仓库。示例见 backend/.env.example。
6. 正式环境使用 JYOTI_ENV=production、ALLOW_LOCAL_LOGIN=0。
   ASTRO_LICENSE_CONFIRMED 为已废弃的旧开关，不再控制运行。
7. 当前数据库默认位于 backend/data（容器为 /app/data），仅适合开发验证。
   正式服务仍需持久化和多实例适配；容器重建会使本地数据丢失。

## 发布对应源码

运行 python3 tools/package_source.py，生成 dist/jyoti-source.zip 和文件清单。
上传该源码包至公开可下载地址，或将解压内容发布为公开仓库并标注对应发布版本。
在 miniprogram/release-config.js 的 sourceUrl 中配置真实公开地址。
“我的 → 隐私与体验说明 → 开源许可与源码”提供复制链接入口。
源码地址必须实际可访问，不能只放一个空仓库；每次部署功能更新应同步对应源码。
部署版本与源码清单 SHA256 应归档，便于核对。

源码包排除 .env、数据库、私人配置、Git 历史、日志及运行时数据。
用户资料、API 密钥不属于应公开的程序源码。
