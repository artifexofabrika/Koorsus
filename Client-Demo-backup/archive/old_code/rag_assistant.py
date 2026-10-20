#!/usr/bin/env python3
"""
RAG Assistant - With DOCX Support
"""

import json
import uuid
import os
from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename

from lake_ingest import ingest_text
from lake_utils import query_lake, get_recent_conversation_context
from web_search import search as web_search

app = Flask(__name__)

HTML = '''
<!DOCTYPE html>
<html>
<head><title>RAG Assistant</title>
<style>
body { font-family: sans-serif; background: #0d1117; color: #e6edf3; margin: 0; padding: 20px; }
#chat { height: 500px; overflow-y: auto; border: 1px solid #30363d; padding: 10px; border-radius: 8px; background: #161b22; }
.message { padding: 8px 12px; margin: 4px 0; border-radius: 8px; }
.user { background: #238636; text-align: right; }
.assistant { background: #21262d; }
.system { background: #1f2937; color: #9ca3af; text-align: center; }
#input-area { display: flex; gap: 10px; margin-top: 10px; }
#input-area textarea { flex: 1; padding: 10px; border-radius: 8px; border: 1px solid #30363d; background: #161b22; color: #e6edf3; }
#input-area button { padding: 10px 20px; background: #238636; border: none; border-radius: 8px; color: white; cursor: pointer; }
#file-area { margin-top: 10px; display: flex; gap: 10px; align-items: center; }
#file-area label { padding: 6px 14px; background: #21262d; border: 1px solid #30363d; border-radius: 6px; cursor: pointer; }
#file-status { font-size: 14px; color: #8b949e; }
.success { color: #3fb950; }
.error { color: #f85149; }
</style>
</head>
<body>
<h2>RAG Assistant</h2>
<div id="chat"></div>
<div id="file-area">
    <label for="file-input">Upload Document</label>
    <input type="file" id="file-input" style="display:none;">
    <span id="file-status">Ready</span>
</div>
<div id="input-area">
    <textarea id="user-input" rows="2" placeholder="Ask a question..."></textarea>
    <button id="send-btn">Send</button>
</div>
<script>
const chat = document.getElementById('chat');
const input = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const fileInput = document.getElementById('file-input');
const fileStatus = document.getElementById('file-status');

function addMessage(role, text) {
    const div = document.createElement('div');
    div.className = 'message ' + role;
    div.textContent = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
}

async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    addMessage('user', text);
    sendBtn.disabled = true;

    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });
        const data = await res.json();
        if (data.reply !== undefined) {
            addMessage('assistant', data.reply);
        } else {
            addMessage('assistant', data.error || 'Unknown error');
        }
    } catch (e) {
        addMessage('assistant', 'Network error: ' + e.message);
    }
    sendBtn.disabled = false;
    input.focus();
}

fileInput.addEventListener('change', async function() {
    if (!this.files.length) return;
    const file = this.files[0];
    fileStatus.textContent = 'Uploading...';
    fileStatus.className = '';
    const fd = new FormData();
    fd.append('file', file);
    try {
        const res = await fetch('/upload', { method: 'POST', body: fd });
        const data = await res.json();
        if (data.error) {
            fileStatus.textContent = 'Error: ' + data.error;
            fileStatus.className = 'error';
        } else {
            fileStatus.textContent = 'Success: ' + (data.message || 'Uploaded');
            fileStatus.className = 'success';
            addMessage('system', 'Uploaded: ' + file.name);
        }
    } catch (e) {
        fileStatus.textContent = 'Network error';
        fileStatus.className = 'error';
    }
    this.value = '';
});

sendBtn.addEventListener('click', sendMessage);
input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
addMessage('system', 'Upload a document, then ask questions.');
input.focus();
</script>
</body>
</html>
'''

def extract_text_from_file(filepath):
    """Extract text from various file types."""
    filename = os.path.basename(filepath)
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    # .txt files
    if ext == 'txt':
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    # .docx files
    if ext == 'docx':
        try:
            import docx
            doc = docx.Document(filepath)
            text = '\n'.join([p.text for p in doc.paragraphs])
            return text
        except ImportError:
            return "python-docx not installed. Please run: pip install python-docx"
        except Exception as e:
            return f"Error parsing docx: {str(e)}"
    
    # .doc files (basic - fallback to raw text)
    if ext == 'doc':
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except:
            return "Could not parse .doc file. Please convert to .docx or .txt."
    
    # .pdf files
    if ext == 'pdf':
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(filepath)
            text = '\n'.join([page.extract_text() for page in reader.pages])
            return text
        except ImportError:
            return "PyPDF2 not installed. Please run: pip install PyPDF2"
        except Exception as e:
            return f"Error parsing PDF: {str(e)}"
    
    # .csv, .json, .md
    if ext in ['csv', 'json', 'md', 'xml', 'html']:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    # Fallback: try to read as text
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except:
        return f"Unsupported or binary file: {filename}. Please convert to .txt or .docx."

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/chat', methods=['POST'])
def chat():
    import requests
    data = request.get_json()
    msg = data.get('message', '')
    if not msg:
        return jsonify({'error': 'No message'})

    # Web search
    if msg.lower().startswith('search the web'):
        query = msg[15:].strip()
        if not query:
            return jsonify({'reply': 'Please specify what you want me to search for.'})
        result = web_search(query, max_results=3)
        if not result:
            return jsonify({'reply': 'No results found.'})
        reply = "\n\n".join([f"{r.get('title','')}: {r.get('snippet','')}" for r in result])
        return jsonify({'reply': reply or 'No results.'})

    # Query the knowledge lake
    lake_results, score = query_lake(msg, n=5, threshold=0.4)
    context = ''
    if lake_results and len(lake_results) > 0:
        context = "\n\n".join(lake_results[:3])
        print(f"[RAG] Found {len(lake_results)} chunks, using first 3")

    # Build prompt
    prompt_parts = []
    prompt_parts.append("You are a helpful assistant for manufacturing operations. Answer concisely based on the provided information.")
    
    if context:
        if len(context) > 1200:
            context = context[:1200] + "..."
        prompt_parts.append(f"Information from documents:\n{context}")
    
    prompt_parts.append(f"Question: {msg}\nAnswer:")
    prompt = "\n\n".join(prompt_parts)
    
    if len(prompt) > 2000:
        prompt = prompt[:2000] + "\n\nAnswer:"

    print(f"[LLM] Sending prompt of length {len(prompt)}")

    try:
        resp = requests.post(
            'http://localhost:8080/completion',
            json={
                'prompt': prompt,
                'n_predict': 256,
                'temperature': 0.5,
                'top_k': 20,
                'top_p': 0.8,
                'stop': ['\n\nUser:', 'User:', 'user:']
            },
            timeout=60
        )
        if resp.status_code == 200:
            reply = resp.json().get('content', '').strip()
            if not reply:
                reply = "I couldn't generate a response."
            return jsonify({'reply': reply})
        else:
            simple_prompt = f"Question: {msg}\nAnswer:"
            resp2 = requests.post(
                'http://localhost:8080/completion',
                json={'prompt': simple_prompt, 'n_predict': 128, 'temperature': 0.5},
                timeout=30
            )
            if resp2.status_code == 200:
                reply = resp2.json().get('content', '').strip()
                return jsonify({'reply': reply or "I couldn't generate a response."})
            else:
                return jsonify({'error': f'LLM error (status {resp.status_code})'})
    except Exception as e:
        return jsonify({'error': f'LLM error: {str(e)}'})

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join('/tmp', filename)
    file.save(filepath)

    try:
        # Extract text from the file
        text = extract_text_from_file(filepath)
        os.remove(filepath)
        
        if text.startswith("Error") or text.startswith("Could not") or text.startswith("Unsupported"):
            return jsonify({'error': text}), 400
        
        if not text or len(text.strip()) < 10:
            return jsonify({'error': 'Extracted text is too short or empty.'}), 400
        
        # Ingest the extracted text
        count = ingest_text(text, source_name=filename)
        return jsonify({'message': f'Ingested {filename} ({count} chunks)'})
    except Exception as e:
        os.remove(filepath)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("RAG Assistant on http://0.0.0.0:5010")
    app.run(host='0.0.0.0', port=5010, debug=False)
