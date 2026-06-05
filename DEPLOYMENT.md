# FinSight 项目部署指南

## 🌐 GitHub 仓库信息
- **仓库地址**: https://github.com/jujubaochong/Finsight.git
- **本地路径**: `d:\pmproject\finsight`

## 🚀 推送到 GitHub

### 方法1：使用 HTTPS（最简单）
```bash
cd d:\pmproject\finsight

# 配置远程仓库
git remote add origin https://github.com/jujubaochong/Finsight.git
git branch -M main

# 推送代码（需要 GitHub 凭证）
git push -u origin main
```

### 方法2：使用 GitHub 个人访问令牌
如果遇到认证问题，使用令牌：

1. **生成令牌**：
   - 访问 https://github.com/settings/tokens
   - 点击 "Generate new token"
   - 选择 `repo` 权限
   - 复制生成的令牌

2. **推送代码**：
   ```bash
   git push -u origin main
   ```
   - 用户名：你的 GitHub 用户名
   - 密码：粘贴生成的令牌（不是 GitHub 密码）

### 方法3：使用 SSH（推荐用于生产）
```bash
# 1. 生成 SSH 密钥（如果还没有）
ssh-keygen -t ed25519 -C "your_email@example.com"

# 2. 将公钥添加到 GitHub
#    - 复制 ~/.ssh/id_ed25519.pub 内容
#    - 添加到 https://github.com/settings/keys

# 3. 使用 SSH 地址
git remote set-url origin git@github.com:jujubaochong/Finsight.git
git push -u origin main
```

## 🔧 项目结构已准备
本地仓库包含：
- ✅ 67 个文件已提交
- ✅ README.md 项目文档
- ✅ .gitignore 配置文件
- ✅ 完整的后端代码（Python + FastAPI）
- ✅ 完整的前端代码（React + TypeScript）
- ✅ 项目文档（docs/ 目录）
- ✅ 部署脚本和指南

## 📦 项目包含的功能
1. **股票数据分析系统**
2. **AI 智能分析**（使用 DeepSeek API）
3. **实时异动监控**
4. **行业对标分析**
5. **现代化前端界面**
6. **后台任务调度**
7. **缓存和错误处理机制**

## 🌍 在线访问
推送成功后，项目将在：
- **GitHub 仓库**: https://github.com/jujubaochong/Finsight
- **GitHub Pages**（可选）: https://jujubaochong.github.io/Finsight/

## 🛠️ 后续步骤

### 1. 设置 GitHub Actions（CI/CD）
在 `.github/workflows/` 中添加工作流文件，实现自动测试和部署。

### 2. 配置 GitHub Pages
```yaml
# 在仓库 Settings → Pages 中配置
# Source: GitHub Actions 或 main 分支
```

### 3. 添加项目徽章
在 README.md 中添加：
```markdown
![GitHub last commit](https://img.shields.io/github/last-commit/jujubaochong/Finsight)
![GitHub stars](https://img.shields.io/github/stars/jujubaochong/Finsight)
```

### 4. 设置 Issues 和 Discussions
启用 GitHub 的项目管理功能。

## 🆘 常见问题解决

### Q: 推送时出现 "Connection timed out"
**解决方案**：
1. 检查网络连接
2. 使用 VPN（如果需要）
3. 尝试 SSH 方式
4. 使用 GitHub CLI

### Q: 需要用户名密码，但不想每次都输入
**解决方案**：
```bash
# 保存凭证
git config --global credential.helper manager
```

### Q: 如何克隆到其他机器
```bash
git clone https://github.com/jujubaochong/Finsight.git
cd Finsight
```

## 📞 技术支持
如果遇到问题：
1. 检查 GitHub 文档
2. 查看 Git 错误信息
3. 搜索相关错误解决方案

---

**项目已准备就绪，等待推送到 GitHub！** 🚀