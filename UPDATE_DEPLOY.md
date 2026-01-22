# 更新现有部署到新版本

如果你的服务器上已经部署了别人的 sora2api 版本，可以按照以下步骤更新到你的版本。

## 🔄 更新步骤

### 方式一：更新远程仓库并拉取（推荐）

**1. SSH 连接到服务器**

```bash
ssh root@your-server-ip
# 或
ssh user@your-server-ip
```

**2. 进入项目目录**

```bash
# 找到项目目录（通常在以下位置之一）
cd /root/sora2api
# 或
cd /home/user/sora2api
# 或
cd ~/sora2api

# 如果不知道位置，可以搜索
find / -name "sora2api" -type d 2>/dev/null
```

**3. 备份当前配置和数据库**

```bash
# 进入项目目录
cd /path/to/sora2api

# 备份配置文件
cp config/setting.toml config/setting.toml.backup

# 备份数据库
cp data/hancat.db data/hancat.db.backup

# 或备份整个 data 目录
cp -r data data.backup
```

**4. 更新远程仓库地址**

```bash
# 查看当前远程仓库
git remote -v

# 更新为你的仓库
git remote set-url origin https://github.com/432539/sora2api.git

# 验证
git remote -v
```

**5. 拉取最新代码**

```bash
# 获取最新代码
git fetch origin

# 查看当前分支
git branch

# 拉取并合并（如果有冲突需要处理）
git pull origin main

# 如果出现冲突，先暂存本地更改
git stash
git pull origin main
git stash pop
```

**6. 更新依赖（如果使用 Python 方式）**

```bash
# 如果使用 Python 直接部署
source venv/bin/activate
pip install -r requirements.txt
```

**7. 恢复配置文件**

```bash
# 如果配置文件被覆盖，恢复你的配置
cp config/setting.toml.backup config/setting.toml

# 或手动合并配置
nano config/setting.toml
```

**8. 重启服务**

**Docker 方式：**
```bash
docker-compose down
docker-compose up -d
docker-compose logs -f
```

**Python 方式：**
```bash
sudo systemctl restart sora2api
sudo systemctl status sora2api
sudo journalctl -u sora2api -f
```

---

### 方式二：完全重新部署（如果更新失败）

如果更新过程中遇到问题，可以完全重新部署：

**1. 备份重要数据**

```bash
# 备份数据库
cp /path/to/sora2api/data/hancat.db ~/hancat.db.backup

# 备份配置
cp /path/to/sora2api/config/setting.toml ~/setting.toml.backup
```

**2. 停止旧服务**

```bash
# Docker 方式
cd /path/to/sora2api
docker-compose down

# Python 方式
sudo systemctl stop sora2api
```

**3. 删除或重命名旧项目**

```bash
# 重命名旧项目（保留作为备份）
mv /path/to/sora2api /path/to/sora2api.old

# 或直接删除（如果确定不需要）
# rm -rf /path/to/sora2api
```

**4. 从你的 GitHub 克隆新项目**

```bash
# 克隆你的仓库
git clone https://github.com/432539/sora2api.git
cd sora2api
```

**5. 恢复配置和数据库**

```bash
# 恢复配置文件
cp ~/setting.toml.backup config/setting.toml

# 恢复数据库
cp ~/hancat.db.backup data/hancat.db

# 确保权限正确
chmod 644 config/setting.toml
chmod 644 data/hancat.db
```

**6. 启动服务**

```bash
# Docker 方式
docker-compose up -d
docker-compose logs -f

# Python 方式
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl start sora2api
```

---

## 📋 更新检查清单

- [ ] 已备份配置文件和数据库
- [ ] 已更新远程仓库地址
- [ ] 已拉取最新代码
- [ ] 已更新依赖（Python 方式）
- [ ] 已恢复配置文件
- [ ] 服务已重启
- [ ] 管理后台可以访问
- [ ] API 可以正常调用
- [ ] Token 数据完整（检查数据库）

---

## ⚠️ 注意事项

### 1. 数据库兼容性

如果数据库结构有变化，系统会自动迁移。但建议先备份：

```bash
# 备份数据库
cp data/hancat.db data/hancat.db.$(date +%Y%m%d_%H%M%S).backup
```

### 2. 配置文件合并

如果 `config/setting.toml` 有新增配置项，需要手动添加：

```bash
# 查看新配置文件的差异
diff config/setting.toml config/setting.toml.backup

# 手动合并或直接使用新配置，然后修改敏感信息
nano config/setting.toml
```

### 3. 端口冲突

如果旧服务还在运行，确保先停止：

```bash
# 检查端口占用
sudo netstat -tlnp | grep 8000

# 停止旧服务
docker-compose down
# 或
sudo systemctl stop sora2api
```

### 4. 环境变量

如果使用了环境变量，确保新版本也配置了：

```bash
# 检查是否有 .env 文件
ls -la .env

# 如果有，备份并检查
cp .env .env.backup
```

---

## 🔧 常见问题

### 1. Git 拉取冲突

```bash
# 如果出现冲突
git status

# 查看冲突文件
git diff

# 解决冲突后
git add .
git commit -m "Merge conflicts resolved"
```

### 2. 数据库迁移失败

```bash
# 检查数据库文件
ls -la data/hancat.db

# 如果数据库损坏，从备份恢复
cp data/hancat.db.backup data/hancat.db

# 重启服务，让系统重新初始化
docker-compose restart
# 或
sudo systemctl restart sora2api
```

### 3. 服务无法启动

```bash
# 查看详细日志
docker-compose logs -f
# 或
sudo journalctl -u sora2api -f

# 检查配置文件语法
python3 -c "import tomli; tomli.load(open('config/setting.toml', 'rb'))"
```

---

## 🚀 快速更新命令（一键更新）

**Docker 方式：**

```bash
cd /path/to/sora2api
cp config/setting.toml config/setting.toml.backup
cp data/hancat.db data/hancat.db.backup
git remote set-url origin https://github.com/432539/sora2api.git
git fetch origin
git pull origin main
cp config/setting.toml.backup config/setting.toml
docker-compose down
docker-compose up -d
docker-compose logs -f
```

**Python 方式：**

```bash
cd /path/to/sora2api
cp config/setting.toml config/setting.toml.backup
cp data/hancat.db data/hancat.db.backup
git remote set-url origin https://github.com/432539/sora2api.git
git fetch origin
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
cp config/setting.toml.backup config/setting.toml
sudo systemctl restart sora2api
sudo journalctl -u sora2api -f
```

---

**更新完成后，访问 `http://your-server-ip:8000/manage` 验证功能正常！**
