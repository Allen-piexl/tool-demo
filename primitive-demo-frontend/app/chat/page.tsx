'use client';
import { useState } from 'react';

type Message = { role: 'user' | 'assistant'; content: string };

export default function ChatPage() {
  const [input, setInput] = useState('What is AAPL stock price?');
  const [messages, setMessages] = useState<Message[]>([{ role:'assistant', content:'Hello, how can I help you today?' }]);
  const [trace, setTrace] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  async function send() {
    const query = input.trim();
    if (!query || loading) return;
    setMessages(m => [...m, { role:'user', content: query }]);
    setInput('');
    setLoading(true);
    setTrace([{ step:'Sending request to router', status:'running', detail: query }]);
    try {
      const res = await fetch('/api/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ query }) });
      const data = await res.json();
      setTrace(data.trace || []);
      setMessages(m => [...m, { role:'assistant', content: data.answer || 'No answer returned.' }]);
    } catch (e:any) {
      setTrace([{ step:'Request failed', status:'error', detail: String(e.message || e) }]);
      setMessages(m => [...m, { role:'assistant', content:'Request failed.' }]);
    } finally { setLoading(false); }
  }

  return <main className="container"><div className="chatLayout"><section className="panel"><div className="panelHead">Chat</div><div className="messages">{messages.map((m,i)=><div key={i} className={`msg ${m.role==='user'?'user':'assistant'}`}>{m.content}</div>)}{loading && <div className="msg assistant">Thinking and routing...</div>}</div><div className="inputbar"><input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')send()}} placeholder="Ask something..."/><button onClick={send}>{loading?'...':'Send'}</button></div></section><aside className="panel"><div className="panelHead">Execution Trace</div><div className="trace">{trace.length===0 ? <p className="muted">Router decisions and primitive calls will appear here.</p> : trace.map((t,i)=><div className="traceItem" key={i}><div className="traceTop"><b>{t.step}</b><span className={`badge ${t.status}`}>{t.status}</span></div><div className="raw">{typeof t.detail === 'string' ? t.detail : JSON.stringify(t.detail,null,2)}</div></div>)}</div></aside></div></main>;
}
