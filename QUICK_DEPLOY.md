# 快速部署指南

从 GitHub 部署到服务器的快速步骤。

## 🚀 快速部署步骤

### 前提条件
- 已购买 Linux 服务器（Ubuntu/CentOS/Debian）
- 已获取服务器 IP 和 SSH 登录信息
- 服务器可以访问 GitHub

---

## 方式一：Docker 部署（推荐，最简单）

### 1. SSH 连接到服务器

```bash
# 在本地 PowerShell 或 CMD 中
ssh root@your-server-ip
# 或
ssh user@your-server-ip
```

### 2. 安装 Docker 和 Docker Compose

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 验证安装
docker --version
docker-compose --version
```

### 3. 从 GitHub 克隆项目

```bash
# 克隆你的仓库
git clone https://github.com/432539/sora2api.git
cd sora2api
```

### 4. 配置项目

```bash
# 编辑配置文件
nano config/setting.toml
```

**重要配置项：**
```toml
[global]
api_key = "your-secure-api-key"  # 修改为安全的 API Key
admin_username = "admin"
admin_password = "your-secure-password"  # 修改为安全的密码

[server]
host = "0.0.0.0"  # 监听所有网络接口
port = 8000
```

保存：`Ctrl + O`，回车，`Ctrl + X`

### 5. 启动服务

```bash
# 启动 Docker 容器
docker-compose up -d

# 查看日志
docker-compose logs -f

# 查看运行状态
docker-compose ps
```

### 6. 验证部署

```bash
# 在服务器上测试
curl http://localhost:8000

# 或从本地浏览器访问
# http://your-server-ip:8000/manage
```

### 7. 配置防火墙（如果需要）

```bash
# Ubuntu/Debian
sudo ufw allow 8000/tcp
sudo ufw enable

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

---

## 方式二：Python 直接部署

### 1. SSH 连接到服务器

```bash
ssh user@your-server-ip
```

### 2. 安装 Python 和依赖

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3 python3-pip python3-venv build-essential libssl-dev libffi-dev git

# CentOS/RHEL
sudo yum install -y python3 python3-pip git
sudo yum groupinstall -y "Development Tools"
sudo yum install -y openssl-devel libffi-devel
```

### 3. 从 GitHub 克隆项目

```bash
git clone https://github.com/432539/sora2api.git
cd sora2api
```

### 4. 创建虚拟环境并安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 5. 配置项目

```bash
nano config/setting.toml
# 修改 api_key 和 admin_password
```

### 6. 使用 systemd 管理服务（后台运行）

创建服务文件：

```bash
sudo nano /etc/systemd/system/sora2api.service
```

添加以下内容（**修改路径为实际路径**）：

```ini
[Unit]
Description=Sora2API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/sora2api
Environment="PATH=/root/sora2api/venv/bin"
ExecStart=/root/sora2api/venv/bin/python /root/sora2api/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
# 重新加载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start sora2api

# 设置开机自启
sudo systemctl enable sora2api

# 查看状态
sudo systemctl status sora2api

# 查看日志
sudo journalctl -u sora2api -f
```

---

## 🌐 配置 Nginx 反向代理（推荐）

### 1. 安装 Nginx

```bash
# Ubuntu/Debian
sudo apt install -y nginx

# CentOS/RHEL
sudo yum install -y nginx
```

### 2. 创建配置文件

```bash
sudo nano /etc/nginx/sites-available/sora2api
```

添加配置：

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 修改为你的域名或 IP

    # 客户端最大请求体大小（用于上传图片/视频）
    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置（视频生成可能需要较长时间）
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

### 3. 启用配置

```bash
# Ubuntu/Debian
sudo ln -s /etc/nginx/sites-available/sora2api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# CentOS/RHEL
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🔒 配置 SSL/HTTPS（可选）

### 使用 Let's Encrypt 免费证书

```bash
# 安装 Certbot
# Ubuntu/Debian
sudo apt install -y certbot python3-certbot-nginx

# CentOS/RHEL
sudo yum install -y certbot python3-certbot-nginx

# 申请证书（需要域名）
sudo certbot --nginx -d your-domain.com
```

---

## 📋 部署检查清单

- [ ] 服务器已连接（SSH）
- [ ] Docker/Python 已安装
- [ ] 项目已从 GitHub 克隆
- [ ] `config/setting.toml` 已配置（API Key、密码）
- [ ] 服务已启动
- [ ] 防火墙已配置（端口 8000）
- [ ] Nginx 已配置（可选）
- [ ] 管理后台可访问：`http://your-server-ip:8000/manage`
- [ ] API 可正常调用

---

## 🔧 常用命令

### Docker 方式

```bash
# 进入项目目录
cd sora2api

# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f

# 更新代码（重新拉取）
git pull
docker-compose up -d --build
```

### Python 方式

```bash
# 进入项目目录
cd sora2api

# 激活虚拟环境
source venv/bin/activate

# 更新代码
git pull
pip install -r requirements.txt

# 重启服务
sudo systemctl restart sora2api

# 查看日志
sudo journalctl -u sora2api -f
```

---

## ❓ 常见问题

### 1. 无法连接服务器

- 检查服务器 IP 是否正确
- 检查 SSH 端口是否开放（默认 22）
- 检查防火墙设置

### 2. 服务无法启动

```bash
# Docker 方式
docker-compose logs -f

# Python 方式
sudo journalctl -u sora2api -f
```

### 3. 端口被占用

```bash
# 检查端口占用
sudo netstat -tlnp | grep 8000

# 修改 config/setting.toml 中的端口
```

### 4. 无法访问管理后台

- 检查防火墙是否开放 8000 端口
- 检查服务是否运行
- 检查 Nginx 配置（如果使用）

---

## 🎯 推荐部署流程

1. **使用 Docker 方式**（最简单，推荐）
2. **配置 Nginx 反向代理**（提升性能和安全性）
3. **配置 SSL/HTTPS**（如果使用域名）
4. **定期备份数据库**（`data/hancat.db`）

---

**部署完成后，访问 `http://your-server-ip:8000/manage` 进行初始配置！**
