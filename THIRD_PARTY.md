# 第三方组件与服务

本项目原创程序代码按 AGPL-3.0-or-later 提供，完整许可见根目录 LICENSE。
第三方组件保留其各自许可证和版权声明，不能用本项目声明覆盖。

| 组件 | 直接依赖版本 | 许可证／来源 |
| --- | --- | --- |
| pyswisseph | 2.10.3.2 | AGPL；third_party 中附原始源码及其声明 |
| Swiss Ephemeris | 随上述源码捆绑 | 本项目采用 AGPL 路线；以源码内声明为准 |
| FastAPI | 0.141.1 | MIT；https://github.com/fastapi/fastapi |
| Uvicorn | 0.52.4 | BSD-3-Clause；https://github.com/encode/uvicorn |
| HTTPX | 0.28.1 | BSD-3-Clause；https://github.com/encode/httpx |
| tzdata | 2026.3 | 包装代码 Apache-2.0，时区数据包含公有领域内容；https://github.com/python/tzdata |

依赖安装以 backend/requirements.txt 为准；间接依赖由包管理器解析，各自版权声明随包分发。
本源码包不是 Python/Debian 完整容器镜像的源码镜像。若另行分发容器镜像，应核查镜像内组件的对应分发义务。

微信 SDK／云托管、腾讯地图、DeepSeek 为第三方平台或服务，不因本项目开源而改变其服务条款。
源码中的环境 ID、AppID 是服务标识，不是可供第三方复用的服务授权。
