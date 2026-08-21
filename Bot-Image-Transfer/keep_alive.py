import os
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is active!"

def run():
    # Renderが指定するPORT環境変数を取得（無ければ10000番ポート）
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    """Botとは別にバックグラウンドでWebサーバーを起動する"""
    t = Thread(target=run)
    t.daemon = True
    t.start()
