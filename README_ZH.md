<div align="center">
  <img src="web/static/logos/memos_logo_512.png" width="250"/>
</div>

[English](README.md) | 简体中文

# Memos

Memos 是一个专注于隐私的被动记录项目。它可以自动记录屏幕内容，构建智能索引，并提供便捷的 web 界面来检索历史记录。

这个项目大量参考了另外的两个项目，一个叫做 [Rewind](https://www.rewind.ai/)，另一个叫做 [Windows Recall](https://support.microsoft.com/en-us/windows/retrace-your-steps-with-recall-aa03f8a0-a78b-4b3e-b0a1-2eb8ac48701c)。不过，和他们两者不同，Memos 让你可以完全管控自己的数据，避免将数据传递到不信任的数据中心。

## 快速开始

### 1. 安装 Memos

```sh
pip install -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple memos
```

### 2. 初始化

初始化 memos 的配置文件和 sqlite 数据库：

```sh
memos init
```

数据将存放在 `~/.memos` 目录中。

### 3. 启动服务

```sh
memos start
```

这个命令会：

- 开始对所有屏幕进行记录
- 启动 Web 服务

### 4. 访问 Web 界面

打开浏览器，访问 `http://localhost:8839`

- 默认用户名：`admin`
- 默认密码：`changeme`
