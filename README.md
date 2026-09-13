# 星序.JYOTI

微信小程序前端和 Python 排盘服务源码。原创代码采用 GNU AGPL v3 或更新版本，详见 [LICENSE](LICENSE)、[NOTICE](NOTICE) 和 [第三方说明](THIRD_PARTY.md)。

## 项目结构

- `miniprogram/`：微信小程序。
- `backend/`：FastAPI 服务、计算引擎与外部服务接入。
- `tests/`：前端检查；`backend/tests/`：后端测试。
- `third_party/`：对应版本 pyswisseph 上游源码及校验信息。
- `tools/`：源码打包工具。

## 配置与部署

1. 微信开发者工具导入仓库根目录，修改 `project.config.json` 的 AppID，配置 `miniprogram/release-config.js` 的云环境与服务名。
2. 后端依赖 Python 3.12。执行 `python -m pip install -r backend/requirements.txt`，或 `docker build -t jyoti-api ./backend`。
3. 参考 `backend/.env.example` 在云托管环境变量中填写自己的凭证，服务端口为 `8000`。真实凭证禁止提交 Git 或加入镜像。
4. 授权确认、对应源码发布及运行限制见 [SOURCE_RELEASE.md](SOURCE_RELEASE.md)。

AppID、云环境 ID 和服务名是配置标识，不是 AppSecret；不得把 API 密钥放入小程序前端。

会员存储支持 MySQL，配置、旧数据迁移与验收见 [MEMBER_STORAGE.md](MEMBER_STORAGE.md)。默认 SQLite 仅用于开发；临时状态仍需单实例。此仓库公开不代表已完成生产上线验收。

## 检查与源码包

执行 `node tests/smoke.js`、`node tests/region.js`、`node tests/cloud-api.js` 和 `node tests/release-check.js`。
执行 `python3 tools/package_source.py` 生成 `dist/jyoti-source.zip`。发布前还须检查提交历史、配置及新增文件，打包检查不保证识别所有未知凭证。
