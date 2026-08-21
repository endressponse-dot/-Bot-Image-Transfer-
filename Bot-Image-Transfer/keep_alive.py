import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        # コンソールログを出力しないように抑制
        return

def run():
    # Renderが指定するPORT環境変数を取得（なければ10000番）
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), KeepAliveHandler)
    server.serve_forever()

def keep_alive():
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()
