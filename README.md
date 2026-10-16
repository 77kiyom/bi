# 抖快渠道销售看板

网易有数 BI 抖音订单数据 → 按业务组汇总的每日自动更新 HTML 看板。

- 线上看板（GitHub Pages）：仓库 Settings → Pages → Source 选 `main` / `/docs`。
- 手动更新：仓库 Actions → 「更新抖快看板」→ Run workflow；看板页面上的「手动更新」按钮即跳到这里。
- 每天 11:30（北京时间）自动更新一次。

## 首次配置
1. 仓库 Settings → Secrets and variables → Actions → New repository secret：
   - Name: `BI_TOKEN_KEY`
   - Value: 你的网易有数 tokenKey（本地 config.json 里的 token_key）
2. Settings → Pages → Source = Deploy from a branch → `main` → `/docs`。

## 本地跑
```bash
python daily_update.py --skip-upload   # 拉 BI + 生成
```
