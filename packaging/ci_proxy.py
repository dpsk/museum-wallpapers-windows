"""CI only: serves a PAC file and an HTTP CONNECT proxy on 127.0.0.1 and logs
each host it tunnels to, so CI can check that the built app follows a PAC
file the way Windows does (company networks that refuse direct connections).

    python packaging/ci_proxy.py --port 8899 --log proxy.log
"""

import argparse
import http.server
import select
import socket
import threading


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/proxy.pac":
            self.send_error(404)
            return
        port = self.server.server_address[1]
        body = f'function FindProxyForURL(url, host) {{ return "PROXY 127.0.0.1:{port}"; }}\n'.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ns-proxy-autoconfig")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_CONNECT(self):
        host, _, port = self.path.rpartition(":")
        with self.server.log_lock, open(self.server.log_path, "a", encoding="utf-8") as log:
            log.write(f"{host}\n")
        try:
            upstream = socket.create_connection((host, int(port)), timeout=30)
        except OSError:
            self.send_error(502)
            return
        self.send_response(200, "Connection established")
        self.end_headers()
        client = self.connection
        with upstream:
            while True:
                ready, _, broken = select.select([client, upstream], [], [client, upstream], 120)
                if broken or not ready:
                    return
                for sock in ready:
                    data = sock.recv(65536)
                    if not data:
                        return
                    (upstream if sock is client else client).sendall(data)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--log", required=True)
    args = parser.parse_args()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.log_path = args.log
    server.log_lock = threading.Lock()
    server.serve_forever()


if __name__ == "__main__":
    main()
