import os
import logging
from flask import Flask
from threading import Thread

# ログ表示を整理
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask('')

@app.route('/')
def home():
    return "Bot status: ONLINE"

def run():
    # Renderが指定するPORT環境変数を優先的に取得（標準は10000）
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
