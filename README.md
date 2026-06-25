# Discord Low-Info Users Analyzer

分析 Discord 频道中**话多但信息量低**的用户，帮助构建 ignore 列表，减少噪音。

## 功能

- 通过 Discord REST API 拉取频道历史消息
- 按消息长度分类：empty / short (<20字符) / medium / long
- 计算每个用户的「低信息率」和「噪音分」
- 排除 KOL / 管理员等重要用户
- 输出排名报告（表格 / JSON）

## 噪音分算法

```
噪音分 = 消息数 × 低信息率
```

例：100条消息、90%废话 → 得分90；10条消息、100%废话 → 得分10。前者优先 ignore。

## 快速开始

```bash
# 默认：最近7天，>=10条消息，>=80%低信息
python3 analyze.py <channel-alias>

# 自定义参数
python3 analyze.py <channel-alias> --days 3 --min-msgs 5 --min-low-info 70

# 输出 JSON
python3 analyze.py <channel-alias> --out report.json --quiet
```

## 配置（全部在本地，不上传 git）

| 配置项 | 路径 | 说明 |
|--------|------|------|
| 频道别名 | `~/.config/discord-cli/channels.yaml` | `discord` CLI 的频道/guild 映射 |
| 排除列表 | `~/.config/discord-low-info/exclude.json` | 自动排除的用户名（KOL、管理员） |

创建排除列表：
```bash
mkdir -p ~/.config/discord-low-info
echo '["kol_user1", "admin_user2"]' > ~/.config/discord-low-info/exclude.json
```

## 依赖

- Python 3.9+
- [`discord` CLI](https://github.com/Rouen007/discord-low-info-users) — 用于拉取消息
- Chrome + Discord 登录 — 用于 token 提取（首次）

## 输出示例

```
================================================================================
Channel: tradingroom | Messages: 1700 | Users: 170
Time: 2026-06-24 16:02 ET → 2026-06-24 23:29 ET (7.5h)
Filter: >= 10 msgs, >= 80.0% low-info
================================================================================

 1. siarandomwalk (Sia)
    Msgs: 88 | Avg chars: 11 | Low-info: 90.9% | Score: 80.0
    Breakdown: empty=0 short=79 medium=9 long=0
    Latest: 06-24 21:27 ET - "看看access问题去"

 2. abdc5195 (abdc0003)
    Msgs: 65 | Avg chars: 10 | Low-info: 92.3% | Score: 60.0
    Breakdown: empty=4 short=56 medium=5 long=0
    Latest: 06-24 23:24 ET - "发疯了 15000 点"
```

## 典型流程

1. 运行分析，获取噪音用户排名
2. 排除 KOL / 管理员（已在 `exclude.json` 中配置）
3. 在 Discord 客户端中逐个右键 → Ignore
4. 定期重新运行，捕获新的噪音账号

## 注意事项

- Discord API 每次最多返回100条消息，CLI 自动分页
- 超活跃频道（>200条/小时）可能只能覆盖几小时
- Discord 的 Ignore 功能是客户端本地的，本工具只负责识别目标
- 推荐排除 KOL：他们可能「吵」但有信号价值

## License

MIT
