# app/ui.py
from fastapi import APIRouter, Response

router = APIRouter()

HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Smart Librarian</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; }
    .card { max-width: 860px; margin: 0 auto; padding: 1.25rem; border: 1px solid #ddd; border-radius: 12px; }
    h1 { margin-top: 0; }
    textarea { width: 100%; min-height: 90px; font-size: 1rem; }
    button { padding: .6rem 1rem; border-radius: 8px; border: 1px solid #333; cursor: pointer; }
    pre { background: #f7f7f9; padding: .75rem; border-radius: 8px; overflow: auto; }
    .muted { color: #666; font-size: .9rem; }
    .title { font-weight: 600; }
  </style>
</head>
<body>
  <div class="card">
    <h1>📚 Smart Librarian</h1>
    <p class="muted">Ask for a recommendation (e.g., "I want a book about friendship and magic").</p>
    <textarea id="q" placeholder="Type your request in English only..."></textarea>
    <div style="margin-top: .75rem;">
      <button onclick="send()">Ask</button>
    </div>
    <div id="out" style="margin-top: 1rem;"></div>
  </div>

  <script>
    async function send() {
      const out = document.getElementById('out');
      out.innerHTML = 'Thinking…';
      const prompt = document.getElementById('q').value;
      try {
        const res = await fetch('/chat', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({prompt})
        });
        const data = await res.json();
        out.innerHTML = `
          <div><span class="title">Recommendation:</span> ${data.recommendation_title ? data.recommendation_title : '(none)'}</div>
          <p>${data.message || ''}</p>
          ${data.summary ? '<div><span class="title">Detailed summary:</span></div><pre>'+data.summary+'</pre>' : ''}
          ${data.sources && data.sources.length ? '<div class="muted">Candidates considered: '+data.sources.map(s=>s.title).join(', ')+'</div>' : ''}
        `;
      } catch (e) {
        out.textContent = 'Error: ' + e;
      }
    }
  </script>
</body>
</html>
"""

@router.get("/", response_class=Response)
def index():
    return Response(content=HTML, media_type="text/html")
