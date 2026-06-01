# ANKUSH HIGH FOLLOW TOOLS 🔥

A Telegram bot that scans Instagram for high-follower accounts whose Gmail username is still available.

## What it does

- Searches Instagram for accounts with **40+ followers**
- Checks if `username@gmail.com` is **available** (not registered)
- Sends a full **hit card** to your Telegram with username, email, followers, posts, reset link

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/ankush-high-follow-bot
cd ankush-high-follow-bot
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set your bot token
```bash
export BOT_TOKEN_2=your_telegram_bot_token_here
```

### 4. Run
```bash
python highfollow_bot.py
```

## Hosting (free, 24/7)

### Railway (recommended)
1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
2. Add env variable: `BOT_TOKEN_2 = your_token`
3. Start command: `pip install -r requirements.txt && python highfollow_bot.py`

### Koyeb (truly free forever)
1. Go to [koyeb.com](https://koyeb.com) → Create App → GitHub
2. Add env variable: `BOT_TOKEN_2 = your_token`
3. Run command: `python highfollow_bot.py`
4. Build command: `pip install -r requirements.txt`

## Bot Commands

| Button / Command | Action |
|---|---|
| 🚀 Start Scan | Start scanning Instagram |
| 🛑 Stop Scan | Stop all workers |
| 📋 All Hits | Show all found hits |
| 📊 Status | Show live stats |
| /start | Show welcome message |

## Hit Card Format

```
ANKUSH HIGH POST TOOLS AND HIGH FOLLOWERS
TOTAL HIT : 1
META : True
USERNAME : someuser
MAIL: s***r@gmail.com
RESET  : https://www.instagram.com/accounts/password/reset/
NAME : Some User
FOLLOWERS : 1500
FOLLOWING: 300
DATE: [N/A]
POST : 45
LINK : https://www.instagram.com/someuser
_______________________________________
BY ~ @z7rnz
```

## Config

Edit these at the top of `highfollow_bot.py`:

```python
WORKERS       = 15   # parallel workers (increase for more speed)
MIN_FOLLOWERS = 40   # minimum followers to qualify as a hit
```

---

**BY ~ @z7rnz**
