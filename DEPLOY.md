# 服务器部署指南

本文档提供详细的服务器部署步骤，包括 Docker 部署和直接 Python 部署两种方式。

## 📤 从本地部署到服务器

### 方式一：使用 Git（推荐）

如果你的代码在 Git 仓库中：

```bash
# 在服务器上克隆
ssh user@your-server-ip
git clone https://github.com/your-repo/sora2api.git
# 或
git clone https://gitee.com/your-repo/sora2api.git
cd sora2api
```

### 方式二：使用 SCP 上传（Windows）

**使用 PowerShell 或 CMD：**

```powershell
# 在 Windows PowerShell 中执行
# 上传整个项目文件夹
scp -r C:\Users\Administrator\Desktop\sora\sora2api user@your-server-ip:/home/user/

# 或者只上传必要的文件（排除 __pycache__ 等）
# 先打包
cd C:\Users\Administrator\Desktop\sora
tar -czf sora2api.tar.gz sora2api --exclude="__pycache__" --exclude="*.pyc" --exclude=".git"
scp sora2api.tar.gz user@your-server-ip:/home/user/

# 在服务器上解压
ssh user@your-server-ip
cd /home/user
tar -xzf sora2api.tar.gz
cd sora2api
```

**使用 WinSCP（图形界面工具）：**

1. 下载安装 WinSCP: https://winscp.net/
2. 连接到服务器（输入服务器 IP、用户名、密码）
3. 将本地 `C:\Users\Administrator\Desktop\sora\sora2api` 文件夹拖拽到服务器目录
4. 等待上传完成

### 方式三：使用 FTP 工具

**使用 FileZilla：**

1. 下载安装 FileZilla: https://filezilla-project.org/
2. 连接到服务器（输入服务器 IP、用户名、密码、端口 22）
3. 将本地项目文件夹上传到服务器

### 方式四：使用 rsync（如果服务器支持）

```bash
# 在 Windows 上安装 Git Bash 或 WSL，然后执行：
rsync -avz --exclude '__pycache__' --exclude '*.pyc' --exclude '.git' \
  C:/Users/Administrator/Desktop/sora/sora2api/ \
  user@your-server-ip:/home/user/sora2api/
```

### 上传后的操作

无论使用哪种方式上传，都需要：

```bash
# 1. SSH 连接到服务器
ssh user@your-server-ip

# 2. 进入项目目录
cd /path/to/sora2api

# 3. 检查文件是否完整
ls -la

# 4. 确保配置文件存在
cat config/setting.toml

# 5. 然后按照下面的部署步骤继续
```

---

## 📋 前置要求

### 服务器要求
- **操作系统**: Linux (Ubuntu 20.04+ / CentOS 7+ / Debian 10+)
- **内存**: 至少 2GB RAM
- **磁盘**: 至少 10GB 可用空间
- **网络**: 能够访问 `sora.chatgpt.com`

### 软件要求
- Docker 和 Docker Compose（推荐方式）
- 或 Python 3.8+（直接部署方式）

---

## 🐳 方式一：Docker 部署（推荐）

### 1. 安装 Docker 和 Docker Compose

#### Ubuntu/Debian
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 验证安装
docker --version
docker-compose --version
```

#### CentOS/RHEL
```bash
# 安装 Docker
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y docker-ce docker-ce-cli containerd.io
sudo systemctl start docker
sudo systemctl enable docker

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. 部署项目

```bash
# 克隆项目（或上传项目文件）
git clone https://github.com/TheSmallHanCat/sora2api.git
cd sora2api

# 或者使用你自己的代码
# 将项目文件上传到服务器，然后进入项目目录
```

### 3. 配置项目

编辑 `config/setting.toml` 文件：

```toml
[global]
api_key = "your-secure-api-key"  # 修改为安全的 API Key
admin_username = "admin"
admin_password = "your-secure-password"  # 修改为安全的密码

[server]
host = "0.0.0.0"  # 监听所有网络接口
port = 8000

# 其他配置根据需要修改...
```

### 4. 启动服务

#### 标准模式（不使用代理）
```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 查看运行状态
docker-compose ps
```

#### WARP 模式（使用代理）
```bash
# 使用 WARP 代理启动
docker-compose -f docker-compose.warp.yml up -d

# 查看日志
docker-compose -f docker-compose.warp.yml logs -f
```

### 5. 验证部署

```bash
# 检查服务是否运行
curl http://localhost:8000

# 或访问管理后台
# http://your-server-ip:8000/manage
```

### 6. 常用 Docker 命令

```bash
# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f

# 更新服务（重新构建镜像）
docker-compose up -d --build

# 清理未使用的资源
docker system prune -a
```

---

## 🐍 方式二：直接 Python 部署

### 1. 安装 Python 和依赖

#### Ubuntu/Debian
```bash
# 安装 Python 3.8+
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# 安装系统依赖（curl_cffi 需要）
sudo apt install -y build-essential libssl-dev libffi-dev
```

#### CentOS/RHEL
```bash
# 安装 Python 3.8+
sudo yum install -y python3 python3-pip

# 安装系统依赖
sudo yum groupinstall -y "Development Tools"
sudo yum install -y openssl-devel libffi-devel
```

### 2. 部署项目

**如果代码已经在服务器上：**

```bash
# 进入项目目录
cd /path/to/sora2api

# 创建虚拟环境
python3 -m venv venv
```

**如果需要从 Git 克隆：**

```bash
# 克隆项目
git clone https://github.com/TheSmallHanCat/sora2api.git
cd sora2api

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置项目

编辑 `config/setting.toml` 文件（同 Docker 方式）

### 4. 使用 systemd 管理服务（推荐）

创建 systemd 服务文件：

```bash
sudo nano /etc/systemd/system/sora2api.service
```

添加以下内容：

```ini
[Unit]
Description=Sora2API Service
After=network.target

[Service]
Type=simple
User=www-data  # 根据实际情况修改用户
WorkingDirectory=/path/to/sora2api  # 修改为实际项目路径
Environment="PATH=/path/to/sora2api/venv/bin"  # 修改为实际虚拟环境路径
ExecStart=/path/to/sora2api/venv/bin/python /path/to/sora2api/main.py
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

### 5. 使用 Supervisor 管理服务（备选）

安装 Supervisor：

```bash
sudo apt install -y supervisor  # Ubuntu/Debian
sudo yum install -y supervisor   # CentOS/RHEL
```

创建配置文件：

```bash
sudo nano /etc/supervisor/conf.d/sora2api.conf
```

添加以下内容：

```ini
[program:sora2api]
command=/path/to/sora2api/venv/bin/python /path/to/sora2api/main.py
directory=/path/to/sora2api
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/sora2api/error.log
stdout_logfile=/var/log/sora2api/access.log
environment=PATH="/path/to/sora2api/venv/bin"
```

启动服务：

```bash
# 创建日志目录
sudo mkdir -p /var/log/sora2api

# 重新加载配置
sudo supervisorctl reread
sudo supervisorctl update

# 启动服务
sudo supervisorctl start sora2api

# 查看状态
sudo supervisorctl status sora2api
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

### 2. 配置 Nginx

创建配置文件：

```bash
sudo nano /etc/nginx/sites-available/sora2api  # Ubuntu/Debian
# 或
sudo nano /etc/nginx/conf.d/sora2api.conf      # CentOS/RHEL
```

添加以下配置：

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

启用配置：

```bash
# Ubuntu/Debian
sudo ln -s /etc/nginx/sites-available/sora2api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# CentOS/RHEL
sudo nginx -t
sudo systemctl restart nginx
```

### 3. 配置 SSL/HTTPS（使用 Let's Encrypt）

安装 Certbot：

```bash
# Ubuntu/Debian
sudo apt install -y certbot python3-certbot-nginx

# CentOS/RHEL
sudo yum install -y certbot python3-certbot-nginx
```

申请 SSL 证书：

```bash
sudo certbot --nginx -d your-domain.com
```

Certbot 会自动配置 Nginx 并设置自动续期。

---

## 🔥 配置防火墙

### Ubuntu/Debian (UFW)

```bash
# 允许 HTTP 和 HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 如果直接访问 8000 端口（不推荐）
sudo ufw allow 8000/tcp

# 启用防火墙
sudo ufw enable
```

### CentOS/RHEL (firewalld)

```bash
# 允许 HTTP 和 HTTPS
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https

# 如果直接访问 8000 端口（不推荐）
sudo firewall-cmd --permanent --add-port=8000/tcp

# 重新加载防火墙
sudo firewall-cmd --reload
```

---

## 📝 部署检查清单

- [ ] Docker/Python 环境已安装
- [ ] 项目文件已上传到服务器
- [ ] `config/setting.toml` 已配置（API Key、密码等）
- [ ] 服务已启动并运行正常
- [ ] 防火墙已配置（如需要）
- [ ] Nginx 反向代理已配置（如需要）
- [ ] SSL 证书已配置（如需要）
- [ ] 管理后台可以访问
- [ ] API 可以正常调用

---

## 🔧 常见问题

### 1. 服务无法启动

**检查日志**：
```bash
# Docker
docker-compose logs -f

# systemd
sudo journalctl -u sora2api -f

# Supervisor
sudo supervisorctl tail -f sora2api
```

### 2. 端口被占用

```bash
# 检查端口占用
sudo netstat -tlnp | grep 8000
# 或
sudo lsof -i :8000

# 修改 config/setting.toml 中的端口
```

### 3. 无法访问服务

- 检查防火墙设置
- 检查服务是否运行：`docker-compose ps` 或 `sudo systemctl status sora2api`
- 检查 Nginx 配置：`sudo nginx -t`

### 4. 数据库文件权限问题

```bash
# 确保 data 目录有写权限
sudo chown -R www-data:www-data data/
sudo chmod -R 755 data/
```

### 5. 内存不足

如果服务器内存较小，可以：
- 减少并发请求数
- 调整 `config/setting.toml` 中的超时设置
- 使用 Docker 限制内存：在 `docker-compose.yml` 中添加 `mem_limit: 2g`

---

## 🚀 性能优化建议

1. **使用 Nginx 反向代理**：提供更好的性能和安全性
2. **启用 HTTPS**：保护数据传输安全
3. **配置日志轮转**：避免日志文件过大
4. **定期备份数据库**：备份 `data/hancat.db` 文件
5. **监控服务状态**：使用 systemd 或 Supervisor 自动重启

---

## 📞 获取帮助

如果遇到问题，可以：
1. 查看项目 README.md
2. 检查日志文件
3. 提交 Issue 到 GitHub

---

**部署完成后，访问 `http://your-server-ip:8000/manage` 进行初始配置！**
