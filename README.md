# 🛰️ Meteosat Europe Bot

**Automatic daily satellite animation of Europe from EUMETSAT’s Meteosat SEVIRI**  
Generated and posted automatically every morning 🌅

<p align="center">
  <img src="docs/example.gif" width="500" alt="Meteosat Europe Natural Colour RGB Example">
</p>

## 🌍 About
This bot downloads and processes **Meteosat SEVIRI Level 1.5** data from the **EUMETSAT Data Store**, generates a **Natural Colour RGB** animation over Europe, and posts it daily on **X (Twitter)**.
- 🕓 Runs automatically every day at **08:30 UTC**
- 🧠 Built with [Satpy](https://satpy.readthedocs.io/)
- 🛰️ Data from [EUMETSAT](https://www.eumetsat.int/)
- 🤖 Deployed via [GitHub Actions](https://github.com/features/actions)

## ⚙️ How it works
1. **Authenticate** with your EUMETSAT API key  
2. **Search & download** SEVIRI HR data (`EO:EUM:DAT:MSG:HRSEVIRI`)  
3. **Process** natural colour RGB composites with `satpy`  
4. **Generate** a daily animation (`.gif`)  
5. **Post** it automatically to X (via `tweepy`)

## 🚀 Run locally
```bash
git clone https://github.com/YOUR_USERNAME/meteosat-europe-bot.git
cd meteosat-europe-bot
pip install -r requirements.txt
python generate_and_post.py
