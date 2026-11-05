"""Servidor HTTP local que imita formularios de ATS. SOLO para pruebas: nunca se contacta a un empleador real."""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = """<html><body><h1>Senior Analyst</h1>
<form method="POST" action="/submit/{v}" enctype="multipart/form-data" id="application_form">
<label for="first_name">First Name *</label><input id="first_name" name="first_name" required>
<label for="last_name">Last Name *</label><input id="last_name" name="last_name" required>
<label for="email">Email *</label><input id="email" name="email" type="email" required>
<label for="phone">Phone *</label><input id="phone" name="phone" required>
<label for="resume">Resume/CV *</label><input id="resume" name="resume" type="file" required>
<label for="cover_letter_text">Cover Letter</label><textarea id="cover_letter_text" name="cover_letter_text"></textarea>
<label for="linkedin">LinkedIn Profile</label><input id="linkedin" name="linkedin">
<label for="gender">Gender</label><select id="gender" name="gender"><option value="">Select...</option><option>Male</option><option>Female</option></select>
{extra}
<button type="submit">Submit Application</button></form>{pie}</body></html>"""

EXTRA = {
    'ok': '', 'noconfirm': '', 'error': '', 'captcha_after': '',
    'captcha': '', 'login': '<label for="pw">Password</label><input id="pw" name="pw" type="password">',
    'legal': '<label for="auth">Are you legally authorized to work in the US? *</label><select id="auth" name="auth" required>'
             '<option value="">Select</option><option>Yes</option><option>No</option></select>',
    'consent': '<label><input type="checkbox" name="privacy" required> I agree to the privacy policy *</label>',
    # Reproduce el formulario real de Greenhouse: la palabra "location" en una pregunta legal
    'authwork': '<label for="aw">Are you authorized to work in the location(s) you selected? *</label><input id="aw" name="aw" required>',
    'combo': '''<label for="loc">Location (City)*</label>
      <input id="loc" name="loc" role="combobox" aria-haspopup="listbox" aria-autocomplete="list" class="select__input" required autocomplete="off">
      <input class="remix-requiredInput" style="position:absolute;opacity:0;width:5px;height:5px" tabindex="-1">
      <ul id="opts" role="listbox" style="display:none"></ul>
      <script>const i=document.getElementById('loc'),u=document.getElementById('opts');
      i.addEventListener('input',()=>{u.innerHTML='';if(i.value.length<2){u.style.display='none';return}
      for(const t of ['Bogotá, Colombia','Medellín, Colombia']){ if(t.toLowerCase().includes(i.value.toLowerCase())){
        const li=document.createElement('li');li.setAttribute('role','option');li.textContent=t;li.style.cursor='pointer';
        li.onclick=()=>{i.value=t;u.style.display='none'};u.appendChild(li)}} u.style.display=u.children.length?'block':'none'})</script>''',
    'combo_invalido': '<label for="x1">Algo oculto</label><input id="x1" name="x1" required style="display:none">',
    'combo_vacio': '''<label for="co">Country*</label>
      <input id="co" name="co" role="combobox" aria-haspopup="listbox" class="select__input" required autocomplete="off">''',
    'extra': '<label for="why">Why do you want to work here? *</label><textarea id="why" name="why" required></textarea>',
}
PIE = {'captcha': '<div class="h-captcha" style="width:300px;height:80px;border:1px solid #000">hCaptcha</div>'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _enviar(self, codigo, html, headers=None):
        cuerpo = html.encode()
        self.send_response(codigo)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(cuerpo)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path.startswith('/form/'):
            v = self.path.split('/')[2].split('?')[0]
            return self._enviar(200, BASE.format(v=v, extra=EXTRA.get(v, ''), pie=PIE.get(v, '')))
        if self.path.startswith('/confirmation'):
            return self._enviar(200, '<html><body><h1>Thank you for applying!</h1><p>Your application has been submitted.</p></body></html>')
        if self.path.startswith('/procesado'):
            return self._enviar(200, '<html><body><p>Request processed.</p></body></html>')
        self._enviar(404, 'no')

    def do_POST(self):
        largo = int(self.headers.get('Content-Length') or 0)
        cuerpo = self.rfile.read(largo)
        v = self.path.split('/')[2]
        self.server.posts.append((v, cuerpo))
        if v == 'noconfirm':
            return self._enviar(302, '', {'Location': '/procesado'})
        if v == 'error':
            return self._enviar(200, BASE.format(v=v, extra='', pie='') +
                                '<div class="error" role="alert">Email address is not valid</div>')
        if v == 'captcha_after':
            return self._enviar(200, BASE.format(v=v, extra='', pie=PIE['captcha']))
        self._enviar(302, '', {'Location': '/confirmation'})


class Servidor:
    def __enter__(self):
        self.srv = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.srv.posts = []
        self.hilo = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.hilo.start()
        self.base = f'http://127.0.0.1:{self.srv.server_address[1]}'
        return self

    def __exit__(self, *a):
        self.srv.shutdown()
        self.srv.server_close()

    @property
    def posts(self):
        return self.srv.posts
