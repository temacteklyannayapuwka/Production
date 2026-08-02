from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import UnixStreamServer
import os

class RequestHandler(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def _index(self):
        with open(os.environ.get('INDEX_PATH'), 'r', encoding='utf8') as f:
            index = f.read()
        return index.encode()

    def do_GET(self):
        self._set_headers()
        self.wfile.write(self._index())


class UnixSocketHTTPServer(UnixStreamServer):
    def get_request(self):
        request, client_address = super(UnixSocketHTTPServer, self).get_request()
        return (request, ["local", 0])


def run_on_port():
    server_address = (os.environ.get('INSTANCE_HOST'), int(os.environ.get('PORT')))
    server = HTTPServer(server_address, RequestHandler)
    print(f"Listening http://{server_address[0]}:{server_address[1]}/")
    server.serve_forever()

def run_on_socket():
    socket = os.environ.get('SOCKET')
    if os.path.exists(socket):
        os.unlink(socket)
    server = UnixSocketHTTPServer(socket, RequestHandler)
    os.chmod(socket, 0o660)
    print(f"Listening {socket}")
    server.serve_forever()


if 'SOCKET' in os.environ:
    run_on_socket()
else:
    run_on_port()
