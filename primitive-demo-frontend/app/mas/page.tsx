'use client';
import { useState } from 'react';

type TraceItem = { step: string; agent?: string; status: string; detail: any };

const examples = [
  'Evaluate whether the trading desk should buy, hold, or avoid AAPL today based on current market data.',
  'Before the market close, check NVDA and debate whether momentum justifies a small long position.',
  'Review TSLA for a short-term trade and include both bullish and bearish arguments.',
  'Prepare a no-trade recommendation for a generic portfolio risk policy without using live market data.'
];

export default function MasPage() {
  const [goal, setGoal] = useState(examples[0]);
  const [answer, setAnswer] = useState('Run the trading desk MAS to see market research, data access, analyst debate, and portfolio decision.');
  const [trace, setTrace] = useState<TraceItem[]>([]);
  const [research, setResearch] = useState<any>(null);
  const [connectorDecision, setConnectorDecision] = useState<any>(null);
  const [connectorResult, setConnectorResult] = useState<any>(null);
  const [debate, setDebate] = useState<any>(null);
  const [pm, setPm] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  async function runMas() {
    if (!goal.trim() || loading) return;
    setLoading(true);
    setAnswer('Trading desk MAS is running...');
    setTrace([{ step: 'Trading desk receives task', agent: 'System', status: 'running', detail: goal }]);
    setResearch(null); setConnectorDecision(null); setConnectorResult(null); setDebate(null); setPm(null);
    try {
      const res = await fetch('/api/mas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal })
      });
      const data = await res.json();
      setTrace(data.trace || []);
      setResearch(data.research || null);
      setConnectorDecision(data.connector_decision || null);
      setConnectorResult(data.connector_result || null);
      setDebate(data.debate || null);
      setPm(data.portfolio_manager || null);
      setAnswer(data.answer || 'No trading desk response returned.');
    } catch (e:any) {
      setTrace([{ step: 'Trading MAS failed', agent: 'System', status: 'error', detail: String(e.message || e) }]);
      setAnswer('Trading MAS failed.');
    } finally {
      setLoading(false);
    }
  }

  return <main className="container">
    <section className="hero">
      <h1>Equity Trading Desk MAS</h1>
      <p>Demo: one agent researches the security and requests data, a debate agent creates bull and bear arguments, and a portfolio manager makes the final risk-aware decision. The data connector layer is hidden behind the MAS.</p>
    </section>

    <div className="tradingMasLayout">
      <section className="panel tradingInputPanel">
        <div className="panelHead">Trading Desk Request</div>
        <div className="formArea">
          <label>Task from user or upstream agent</label>
          <textarea value={goal} onChange={e=>setGoal(e.target.value)} rows={7} />
          <button className="primaryBtn" onClick={runMas}>{loading ? 'Running Trading MAS...' : 'Run Trading Desk MAS'}</button>
          <div className="exampleBox">
            <div className="smallTitle">Example desk tasks</div>
            {examples.map((ex,i)=><button key={i} className="exampleBtn" onClick={()=>setGoal(ex)}>{ex}</button>)}
          </div>
        </div>
      </section>

      <section className="panel agentBoard tradingBoard">
        <div className="panelHead">Live Multi-Agent Workflow</div>
        <div className="workflowScroll">
          <div className="workflowRail">
          <AgentCard name="MarketResearchAgent" title="Frames the trade and requests data" data={research} placeholder="Waiting for market research output." />
          <div className="arrow">→</div>
          <AgentCard name="Data Access Layer" title="Decides whether external data is needed" data={{ decision: connectorDecision, data_result: connectorResult }} placeholder="Waiting for data access decision." />
          <div className="arrow">→</div>
          <AgentCard name="DebateAgent" title="Bull case vs bear case" data={debate} placeholder="Waiting for analyst debate." />
          <div className="arrow">→</div>
          <AgentCard name="PortfolioManagerAgent" title="Final decision and risk controls" data={pm} placeholder="Waiting for portfolio decision." />
        </div>
          </div>
      </section>

      <section className="panel debatePanel">
        <div className="panelHead">Analyst Debate View</div>
        <div className="debateGrid">
          <DebateBox title="Bull Analyst" items={debate?.bull_case} empty="Bull thesis will appear here." />
          <DebateBox title="Bear Analyst" items={debate?.bear_case} empty="Bear thesis will appear here." />
        </div>
        <div className="debateSummary">
          <b>Cross-examination</b>
          <p>{debate?.cross_examination || 'The debate exchange will appear after the MAS runs.'}</p>
          <div className="pillrow">
            <span className="pill">Winner: {debate?.debate_winner || 'pending'}</span>
            <span className="pill">Confidence: {debate?.confidence || 'pending'}</span>
          </div>
        </div>
      </section>

      <section className="panel resultPanel tradingResult">
        <div className="panelHead">Final Desk Decision</div>
        <div className="messages"><div className="msg assistant wide">{answer}</div></div>
      </section>

      <aside className="panel tracePanel tradingTrace">
        <div className="panelHead">Execution Trace</div>
        <div className="trace">
          {trace.length === 0 ? <p className="muted">Market research, data access decision, connector invocation, debate, and final decision will appear here.</p> : trace.map((t,i)=><div className="traceItem" key={i}><div className="traceTop"><b>{t.agent ? `${t.agent}: ${t.step}` : t.step}</b><span className={`badge ${t.status}`}>{t.status}</span></div><div className="raw">{typeof t.detail === 'string' ? t.detail : JSON.stringify(t.detail,null,2)}</div></div>)}
        </div>
      </aside>
    </div>
  </main>;
}

function AgentCard({name,title,data,placeholder}:{name:string;title:string;data:any;placeholder:string}) {
  const hasData = data && JSON.stringify(data) !== '{}';
  return <div className="agentCard workflowCard">
    <div className="agentHeader"><div><b>{name}</b><p>{title}</p></div><span className={`miniDot ${hasData ? 'active' : ''}`} /></div>
    <div className="raw agentRaw">{hasData ? JSON.stringify(data,null,2) : placeholder}</div>
  </div>
}

function DebateBox({ title, items, empty }:{title:string;items?:string[];empty:string}) {
  return <div className="debateBox">
    <h3>{title}</h3>
    {Array.isArray(items) && items.length ? <ul>{items.map((x,i)=><li key={i}>{x}</li>)}</ul> : <p className="muted">{empty}</p>}
  </div>
}
