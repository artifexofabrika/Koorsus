from flask import Flask, request, jsonify, render_template_string
from lake_ingest import ingest_text
from lake_utils import query_lake

app = Flask(__name__)

HTML = '''
<!DOCTYPE html>
<html>
<body>
<h2>RAG Minimal</h2>
<div id="chat" style="height:300px;border:1px solid #ccc;overflow-y:auto;padding:10px;"></div>
<input type="file" id="file-input">
<textarea id="user-input" rows="2" style="width:80%;"></textarea>
<button id="send-btn">Send</button>
<script>
const chat = document.getElementById('chat');
const input = document.getElementById('user-input');
const fileInput = document.getElementById('file-input');

function addMessage(role, text) {
    const div = document.createElement('div');
    div.textContent = role + ': ' + text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
}

async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    addMessage('user', text);

    const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
    });
    const data = await res.json();
    addMessage('assistant', data.reply || data.error || 'No response');
}

fileInput.addEventListener('change', async function() {
    const file = this.files[0];
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/upload', { method: 'POST', body: fd });
    const data = await res.json();
    addMessage('system', data.message || data.error || 'Upload done');
});

sendBtn.addEventListener('click', sendMessage);
input.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); sendMessage(); } });
</script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/chat', methods=['POST'])
def chat():
    msg = request.json.get('message', '')
    if not msg:
        return jsonify({'error': 'No message'})

    results = query_lake(msg, n=3, threshold=0.4)
    context = '\n\n'.join(results[0]) if results[0] else ''

    prompt = f"Answer based on this information:\n{context}\n\nQuestion: {msg}\nAnswer:" if context else f"Question: {msg}\nAnswer:"

    import requests
    try:
        resp = requests.post('http://localhost:8080/completion',
            json={'prompt': prompt, 'n_predict': 128, 'temperature': 0.5}, timeout=30)
        if resp.status_code == 200:
            return jsonify({'reply': resp.json().get('content', '').strip()})
        return jsonify({'error': f'LLM error {resp.status_code}'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    content = file.read().decode('utf-8', errors='ignore')
    count = ingest_text(content, source_name=file.filename)
    return jsonify({'message': f'Ingested {file.filename} ({count} chunks)'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5010, debug=False)
