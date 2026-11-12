"""Уеб интерфейс за малкия модел.

Пускане:  .venv/bin/python app.py
После отвори http://127.0.0.1:7860
"""
import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from chat import model, reply_stream

# По подразбиране е достъпен само от този компютър.
HOST, PORT = os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", 7860))
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "avatar.png"), "rb") as f:
    AVATAR = f.read()

PAGE = r"""<!DOCTYPE html>
<html lang="bg">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Криско Първи</title>
<style>
  :root {
    --bg: #f7f5f0; --surface: #ffffff; --ink: #1d1b18; --muted: #7b766d;
    --line: #e6e1d7; --accent: #f2c500; --accent-2: #ffe14d; --on-accent: #1d1b18;
    --user: #ece7dd; --shadow: 0 1px 2px rgba(40,30,20,.05), 0 8px 28px rgba(40,30,20,.07);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #171614; --surface: #211f1c; --ink: #edeae4; --muted: #9a958b;
      --line: #34312c; --accent: #ffd60a; --accent-2: #ffe866; --on-accent: #1d1b18;
      --user: #2e2b27; --shadow: 0 1px 2px rgba(0,0,0,.3), 0 8px 28px rgba(0,0,0,.35);
    }
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    background: var(--bg); color: var(--ink);
    font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    -webkit-font-smoothing: antialiased;
    display: flex; flex-direction: column;
  }
  button { font: inherit; color: inherit; cursor: pointer; }

  /* Горна лента */
  .top {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 20px; border-bottom: 1px solid var(--line);
  }
  .avatar {
    flex: none; width: 34px; height: 34px; border-radius: 50%;
    background: #fff; object-fit: cover; object-position: 50% 30%;
    border: 2px solid var(--accent); display: block;
  }
  .who { flex: 1; min-width: 0; line-height: 1.25; }
  .who b { display: block; font-size: 15px; font-weight: 650; }
  .who span { font-size: 12.5px; color: var(--muted); }
  .ghost {
    background: none; border: 1px solid var(--line); border-radius: 10px;
    padding: 6px 12px; font-size: 13.5px; white-space: nowrap;
    transition: background .15s, border-color .15s;
  }
  .ghost:hover { background: var(--surface); border-color: var(--muted); }

  /* Разговор */
  #scroll { flex: 1; overflow-y: auto; }
  .col { width: 100%; max-width: 760px; margin: 0 auto; padding: 0 20px; }
  #log { display: flex; flex-direction: column; gap: 22px; padding-top: 28px; padding-bottom: 28px; }
  #log:empty { display: none; }
  .row { display: flex; gap: 12px; animation: rise .28s ease both; }
  @keyframes rise { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
  .row.user { justify-content: flex-end; }
  .row.user .text {
    background: var(--user); padding: 9px 16px; border-radius: 20px 20px 6px 20px; max-width: 78%;
  }
  .row.bot .avatar { width: 32px; height: 32px; margin-top: 0; }
  .row.bot .text { flex: 1; min-width: 0; padding-top: 3px; }
  .text { white-space: pre-wrap; overflow-wrap: anywhere; }
  .row.error .text { color: #c0392b; }
  @media (prefers-color-scheme: dark) { .row.error .text { color: #ef8377; } }

  /* Курсор и "мисли" */
  .caret {
    display: inline-block; width: 9px; height: 1.05em; margin-left: 2px; border-radius: 2px;
    background: var(--accent); vertical-align: text-bottom; animation: blink 1s steps(2, start) infinite;
  }
  @keyframes blink { to { visibility: hidden; } }
  .thinking { display: inline-flex; gap: 5px; align-items: center; height: 1.6em; }
  .thinking i {
    width: 7px; height: 7px; border-radius: 50%; background: var(--muted);
    animation: bounce 1.1s ease-in-out infinite;
  }
  .thinking i:nth-child(2) { animation-delay: .15s; }
  .thinking i:nth-child(3) { animation-delay: .3s; }
  @keyframes bounce { 0%, 60%, 100% { transform: none; opacity: .45; } 30% { transform: translateY(-5px); opacity: 1; } }

  /* Начален екран */
  #welcome { text-align: center; padding: 9vh 0 24px; animation: rise .4s ease both; }
  #welcome[hidden] { display: none; }
  #welcome .avatar { width: 104px; height: 104px; border-width: 3px; margin: 0 auto 20px; box-shadow: var(--shadow); }
  #welcome h1 { font-size: 28px; line-height: 1.2; margin: 0 0 8px; font-weight: 680; letter-spacing: -0.02em; }
  #welcome p { margin: 0 auto; max-width: 440px; color: var(--muted); transition: opacity .2s; }
  #welcome p.gone { opacity: 0; }
  #welcome p { min-height: 1.6em; }
  #welcome .caret { width: 2px; height: 1.1em; border-radius: 1px; }

  /* Поле за писане */
  .dock { padding-bottom: 14px; }
  .composer {
    display: flex; align-items: flex-end; gap: 8px;
    background: var(--surface); border: 1px solid var(--line); border-radius: 26px;
    padding: 8px 8px 8px 20px; box-shadow: var(--shadow); transition: border-color .15s;
  }
  .composer:focus-within { border-color: var(--accent); }
  textarea {
    flex: 1; min-width: 0; resize: none; border: 0; outline: 0; background: none;
    font: inherit; color: inherit; padding: 7px 0; max-height: 140px;
  }
  textarea::placeholder { color: var(--muted); }
  #send {
    flex: none; width: 38px; height: 38px; border-radius: 50%; border: 0;
    background: var(--accent); color: var(--on-accent); display: grid; place-items: center;
    transition: transform .12s, opacity .15s;
  }
  #send:hover:not(:disabled) { transform: scale(1.06); }
  #send:disabled { opacity: .35; cursor: default; }
  .note { text-align: center; font-size: 12px; color: var(--muted); margin: 9px 0 0; }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
</head>
<body>
  <div class="top">
    <img class="avatar" src="/avatar.png" alt="">
    <div class="who">
      <b>Криско Първи</b>
      <span>__PARAMS__ параметъра · __WHERE__</span>
    </div>
    <button class="ghost" id="reset" type="button">Нов чат</button>
  </div>

  <div id="scroll">
    <div class="col">
      <div id="welcome">
        <img class="avatar" src="/avatar.png" alt="">
        <h1>Здравейте, аз съм Криско Първи</h1>
        <p id="hint" aria-label="Започнете разговор с Криско Първи"></p>
      </div>
      <div id="log"></div>
    </div>
  </div>

  <div class="col dock">
    <form class="composer" id="form">
      <textarea id="input" rows="1" placeholder="Напиши съобщение…" autofocus></textarea>
      <button id="send" type="submit" aria-label="Изпрати" disabled>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
      </button>
    </form>
    <p class="note">Криско Първи е първият модел на Кристиян Зайнелов създаден от нулата на 12.11.2026</p>
  </div>

<script>
  const $ = (id) => document.getElementById(id);
  const scroll = $('scroll'), log = $('log'), welcome = $('welcome');
  const form = $('form'), input = $('input'), send = $('send');
  const TYPE_MS = 24;          // пауза между символите при изписване
  let busy = false, session = 0;
  let previous = null;         // предишната размяна {question, answer} – контекстът за модела

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // Откъде идва отговорът: от сървъра (app.py) или, в статичната версия, от модела в браузъра (krisko.js).
  async function* fromServer(message, previous) {
    const res = await fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, previous }),
    });
    if (!res.ok || !res.body) throw new Error('HTTP ' + res.status);
    const stream = res.body.getReader(), decoder = new TextDecoder();
    for (;;) {
      const { value, done } = await stream.read();
      if (done) break;
      yield decoder.decode(value, { stream: true });
    }
  }
  const source = window.kriskoReply || fromServer;

  // Началният текст се изписва буква по буква.
  const HINT = 'Започнете разговор с Криско Първи';
  let hintRun = 0;
  async function typeHint() {
    const run = ++hintRun, hint = $('hint');
    const caret = document.createElement('span'); caret.className = 'caret';
    hint.textContent = ''; hint.appendChild(caret);
    await sleep(450);
    for (const ch of HINT) {
      if (run !== hintRun) return;          // започнато е ново изписване
      caret.before(ch);
      await sleep(ch === ' ' ? 70 : 38 + Math.random() * 40);
    }
    await sleep(1600);
    if (run === hintRun) caret.remove();
  }
  const toBottom = () => { scroll.scrollTop = scroll.scrollHeight; };
  const refresh = () => {
    send.disabled = busy || !input.value.trim();
    $('hint').classList.toggle('gone', input.value.length > 0);   // подсказката изчезва, щом започнеш да пишеш
  };

  function addRow(kind) {
    const row = document.createElement('div'); row.className = 'row ' + kind;
    if (kind === 'bot') {
      const av = document.createElement('img'); av.className = 'avatar'; av.src = '/avatar.png'; av.alt = '';
      row.appendChild(av);
    }
    const text = document.createElement('div'); text.className = 'text';
    row.appendChild(text); log.appendChild(row); toBottom();
    return { row, text };
  }

  async function ask(message) {
    message = message.trim();
    if (!message || busy) return;
    busy = true; const mine = session;
    welcome.hidden = true;
    input.value = ''; input.style.height = 'auto'; refresh();

    addRow('user').text.textContent = message;
    const { row, text } = addRow('bot');
    text.innerHTML = '<span class="thinking"><i></i><i></i><i></i></span>';

    // Мрежата пълни опашката, а екранът я изписва символ по символ.
    let queue = '', done = false, failed = false, shown = '';
    const reader = (async () => {
      try {
        for await (const piece of source(message, previous)) queue += piece;
      } catch (err) { failed = true; }
      done = true;
    })();

    await sleep(350);                       // кратко "мислене" преди първия символ
    const caret = document.createElement('span'); caret.className = 'caret';
    let started = false;
    while (mine === session && (!done || queue)) {
      if (!queue) { await sleep(15); continue; }
      if (!started) { text.textContent = ''; text.appendChild(caret); started = true; }
      const chars = Array.from(queue), ch = chars.shift();
      queue = chars.join(''); shown += ch;
      caret.before(ch); toBottom();
      await sleep(/[.,!?]/.test(ch) ? TYPE_MS * 5 : TYPE_MS);
    }
    await reader;
    if (mine !== session) return;           // междувременно е започнат нов чат

    caret.remove();
    if (failed) {
      row.classList.add('error');
      text.textContent = shown ? shown + ' …(връзката прекъсна)' : 'Моделът не отговори. Опитай пак.';
    } else if (!shown.trim()) {
      text.textContent = '(празен отговор)';
    }
    previous = !failed && shown.trim() ? { question: message, answer: shown.trim() } : null;
    busy = false; refresh(); input.focus(); toBottom();
  }

  form.onsubmit = (e) => { e.preventDefault(); ask(input.value); };
  input.oninput = () => {
    input.style.height = 'auto'; input.style.height = input.scrollHeight + 'px'; refresh();
  };
  input.onkeydown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); ask(input.value); }
  };
  $('reset').onclick = () => {
    session++; busy = false; previous = null; log.textContent = ''; welcome.hidden = false; refresh(); input.focus(); typeHint();
  };

  // Позволява връзка от вида /?q=здрасти, която задава въпроса веднага.
  const preset = new URLSearchParams(location.search).get('q');
  if (preset) ask(preset); else typeHint();
</script>
</body>
</html>
""".replace("__WHERE__", "работи локално").replace("__PARAMS__", f"{model.num_parameters():,}".replace(",", " "))


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type if isinstance(body, bytes) else content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            self._send(200, PAGE, "text/html")
        elif self.path.split("?")[0] == "/avatar.png":
            self._send(200, AVATAR, "image/png")
        else:
            self._send(404, "Not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/chat":
            return self._send(404, "Not found", "text/plain")
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 10_000)
            body = json.loads(self.rfile.read(length))
            message = str(body["message"])[:200]
            previous = body.get("previous") or {}      # предишната размяна, ако има такава
            context = (str(previous.get("question", ""))[:200], str(previous.get("answer", ""))[:200])
        except (ValueError, KeyError, TypeError, AttributeError):
            return self._send(400, json.dumps({"error": "bad request"}), "application/json")

        # Отговорът се праща на парчета, докато моделът го генерира.
        # Без Content-Length: връзката се затваря, когато отговорът свърши.
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            for piece in reply_stream(message, context):
                self.wfile.write(piece.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # браузърът е затворил връзката

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Интерфейсът е на {url}  (Ctrl+C за спиране)")
    if HOST == "127.0.0.1":
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
