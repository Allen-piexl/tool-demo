import { publicRegistry } from '../lib/registry';

export default function ToolsPage() {
  const tools = publicRegistry();
  return <main className="container"><section className="hero"><h1>Available Tool Primitives</h1><p>A product-facing registry of reusable primitives. Internal endpoints and ports are hidden from users.</p></section><section className="grid">{tools.map((t:any)=><article className="card" key={t.id}><div className="status"><span className="dot"/>Online</div><h2>{t.name}</h2><p className="muted">{t.description}</p><div className="pillrow">{t.capabilities.map((c:string)=><span className="pill" key={c}>{c}</span>)}</div><p className="muted"><b>Example:</b> {t.examples?.[0] || 'Ask a task that uses this primitive.'}</p></article>)}</section></main>;
}
