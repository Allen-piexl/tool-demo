import { NextResponse } from "next/server";
import { getRegistry } from "../../lib/registry";

type AgentOutput = Record<string, any>;
type ConnectorDecision = {
  need_external_data: boolean;
  connector_id?: string | null;
  connector_name?: string | null;
  args?: Record<string, any>;
  reason?: string;
  no_data_response?: string;
};

const baseUrl = () => process.env.OLLAMA_BASE_URL || "http://127.0.0.1:11434";
const modelName = () => process.env.OLLAMA_MODEL || "qwen3:8b";

function extractJson(text: string): any {
  const cleaned = String(text || "").replace(/```json|```/g, "").trim();
  const match = cleaned.match(/\{[\s\S]*\}/);
  if (!match) throw new Error("Model did not return JSON");
  return JSON.parse(match[0]);
}

async function callOllamaJson(prompt: string): Promise<any> {
  const res = await fetch(`${baseUrl()}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: modelName(), prompt, stream: false, options: { temperature: 0.2 } })
  });
  if (!res.ok) throw new Error(`Ollama failed: ${res.status}`);
  const data = await res.json();
  return extractJson(data.response || "");
}

function availableConnectors() {
  return getRegistry().map(t => ({
    id: t.id,
    name: t.name.replace("Primitive", "DataConnector"),
    description: t.description,
    capabilities: t.capabilities,
    examples: t.examples
  }));
}

async function marketResearchAgent(task: string): Promise<AgentOutput> {
  const prompt = `You are MarketResearchAgent in an equity trading multi-agent system.
Your job is to interpret the trading desk task and decide what market information should be requested from the data access layer.
Do not mention primitives. Return ONLY valid JSON.

Trading desk task:
${task}

Schema:
{
  "agent": "MarketResearchAgent",
  "desk_task": "one sentence",
  "target_security": "ticker or company if available, otherwise unknown",
  "data_request": "specific request to the data access layer",
  "initial_view": "brief neutral market view before data arrives",
  "handoff_to_debate": "what the bull and bear analysts should debate"
}`;
  return callOllamaJson(prompt);
}

async function dataAccessDecisionAgent(research: AgentOutput): Promise<ConnectorDecision> {
  const prompt = `You are DataAccessPolicy inside a trading MAS.
A MarketResearchAgent may need external data. Decide whether to call one available data connector.
Do not mention primitives. Return ONLY valid JSON.

Available data connectors:
${JSON.stringify(availableConnectors(), null, 2)}

MarketResearchAgent output:
${JSON.stringify(research, null, 2)}

Schema:
{
  "need_external_data": true or false,
  "connector_id": "one available connector id or null",
  "connector_name": "one available connector name or null",
  "args": {"query": "one natural-language string request to connector", "ticker": "if obvious", "context": "short context"},
  "reason": "brief reason",
  "no_data_response": "only when no external data is needed"
}

Rules:
- Use a connector for live/recent market price, ticker lookup, news, search, or other external facts.
- Do not use a connector for generic investment principles or pure internal debate.
- args.query MUST be a single string, never an object or nested JSON.
- For stock quote tasks, prefer the stock connector.
- For recent news/research, prefer the search connector.`;
  return callOllamaJson(prompt);
}

async function debateAgent(task: string, research: AgentOutput, decision: ConnectorDecision, data: any | null): Promise<AgentOutput> {
  const prompt = `You are DebateAgent in an equity trading MAS.
Run an internal analyst debate using the research output and any external data.
Return ONLY valid JSON.

Trading task:
${task}

MarketResearchAgent output:
${JSON.stringify(research, null, 2)}

Data access decision:
${JSON.stringify(decision, null, 2)}

External data result:
${data ? JSON.stringify(data, null, 2) : "No external data was called."}

Schema:
{
  "agent": "DebateAgent",
  "bull_case": ["point 1", "point 2"],
  "bear_case": ["point 1", "point 2"],
  "cross_examination": "one paragraph where the two sides challenge each other",
  "debate_winner": "bull or bear or mixed",
  "confidence": "low or medium or high"
}`;
  return callOllamaJson(prompt);
}

async function portfolioManagerAgent(task: string, research: AgentOutput, debate: AgentOutput, data: any | null): Promise<AgentOutput> {
  const prompt = `You are PortfolioManagerAgent in an equity trading MAS.
Make a cautious final desk recommendation based on the research, debate, and data. This is a demo, not financial advice.
Return ONLY valid JSON.

Trading task:
${task}

Research:
${JSON.stringify(research, null, 2)}

Debate:
${JSON.stringify(debate, null, 2)}

External data:
${data ? JSON.stringify(data, null, 2) : "No external data."}

Schema:
{
  "agent": "PortfolioManagerAgent",
  "action": "buy or sell or hold or no_trade",
  "rationale": "concise rationale",
  "risk_controls": ["risk control 1", "risk control 2"],
  "final_answer": "final response for the MAS UI"
}`;
  return callOllamaJson(prompt);
}

export async function POST(req: Request) {
  const startedAt = Date.now();
  const body = await req.json();
  const task = String(body.goal || body.task || "").trim();
  const trace: any[] = [];
  if (!task) return NextResponse.json({ error: "Missing MAS trading task" }, { status: 400 });

  function fail(status: number, answer: string, extra: Record<string, any> = {}) {
    return NextResponse.json({ answer, error: answer, trace, latency_ms: Date.now() - startedAt, ...extra }, { status });
  }

  function normalizeConnectorQuery(raw: any, research: AgentOutput): string {
    if (typeof raw === "string" && raw.trim()) return raw.trim();
    const ticker = String(research.target_security || "the target security");
    const request = typeof research.data_request === "string" ? research.data_request : JSON.stringify(research.data_request || {});
    return `For ${ticker}, ${request}. Return the most relevant market data for the trading desk.`;
  }

  trace.push({ step: "Trading desk receives task", agent: "System", status: "done", detail: task });

  let research: AgentOutput;
  try {
    trace.push({ step: "MarketResearchAgent frames the trade", agent: "MarketResearchAgent", status: "running", detail: "Parsing security, objective, and data needs." });
    research = await marketResearchAgent(task);
    trace[trace.length - 1] = { step: "MarketResearchAgent frames the trade", agent: "MarketResearchAgent", status: "done", detail: research };
  } catch (e: any) {
    trace[trace.length - 1] = { step: "MarketResearchAgent frames the trade", agent: "MarketResearchAgent", status: "error", detail: String(e.message || e) };
    return fail(502, "MarketResearchAgent failed. The MAS run stopped immediately.");
  }

  let connectorDecision: ConnectorDecision;
  try {
    trace.push({ step: "DataAccessPolicy decides connector use", agent: "MarketResearchAgent", status: "running", detail: "Checking whether the MAS needs external data." });
    connectorDecision = await dataAccessDecisionAgent(research);
    trace[trace.length - 1] = { step: "DataAccessPolicy decides connector use", agent: "MarketResearchAgent", status: "done", detail: connectorDecision };
  } catch (e: any) {
    trace[trace.length - 1] = { step: "DataAccessPolicy decides connector use", agent: "MarketResearchAgent", status: "error", detail: String(e.message || e) };
    return fail(502, "DataAccessPolicy failed. The MAS run stopped immediately.", { research });
  }

  let connectorResult: any | null = null;
  let selectedConnector: any = null;
  if (connectorDecision.need_external_data) {
    const registry = getRegistry();
    const connector = registry.find(t => t.id === connectorDecision.connector_id || t.name === connectorDecision.connector_name || t.name.replace("Primitive", "DataConnector") === connectorDecision.connector_name);
    if (!connector) {
      trace.push({ step: "Data connector lookup", agent: "System", status: "error", detail: "Selected connector is not registered." });
      return fail(500, "The MAS selected a connector that is not registered.", { research, connector_decision: connectorDecision });
    }

    selectedConnector = { id: connector.id, name: connector.name.replace("Primitive", "DataConnector") };
    const connectorQuery = normalizeConnectorQuery(connectorDecision.args?.query, research);
    const connectorPayload = {
      ...(connectorDecision.args || {}),
      query: connectorQuery,
      context: connectorDecision.args?.context || research.handoff_to_debate || "",
      ticker: connectorDecision.args?.ticker || research.target_security,
      mas_task: task
    };

    trace.push({ step: "Data connector lookup", agent: "System", status: "done", detail: selectedConnector });
    trace.push({ step: "MarketResearchAgent calls data connector", agent: "MarketResearchAgent", status: "running", detail: { selected: selectedConnector.name, payload: connectorPayload } });

    try {
      const invoke = await fetch(connector.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(connectorPayload)
      });
      connectorResult = await invoke.json().catch(() => ({ raw: "Connector returned non-JSON response." }));
      trace[trace.length - 1] = { step: "MarketResearchAgent calls data connector", agent: "MarketResearchAgent", status: invoke.ok ? "done" : "error", detail: { selected: selectedConnector.name, status: invoke.status, result: connectorResult } };
      if (!invoke.ok) {
        return fail(502, `Data connector call failed with status ${invoke.status}. The MAS run stopped immediately.`, { research, connector_decision: connectorDecision, selected_connector: selectedConnector, connector_result: connectorResult });
      }
    } catch (e: any) {
      trace[trace.length - 1] = { step: "MarketResearchAgent calls data connector", agent: "MarketResearchAgent", status: "error", detail: String(e.message || e) };
      return fail(502, "Data connector call failed. The MAS run stopped immediately.", { research, connector_decision: connectorDecision, selected_connector: selectedConnector });
    }
  } else {
    trace.push({ step: "MarketResearchAgent skips external data", agent: "MarketResearchAgent", status: "done", detail: connectorDecision.reason || connectorDecision.no_data_response || "No connector needed." });
  }

  let debate: AgentOutput;
  try {
    trace.push({ step: "DebateAgent runs bull vs bear debate", agent: "DebateAgent", status: "running", detail: "Creating opposing analyst arguments." });
    debate = await debateAgent(task, research, connectorDecision, connectorResult);
    trace[trace.length - 1] = { step: "DebateAgent runs bull vs bear debate", agent: "DebateAgent", status: "done", detail: debate };
  } catch (e: any) {
    trace[trace.length - 1] = { step: "DebateAgent runs bull vs bear debate", agent: "DebateAgent", status: "error", detail: String(e.message || e) };
    return fail(502, "DebateAgent failed. The MAS run stopped immediately.", { research, connector_decision: connectorDecision, selected_connector: selectedConnector, connector_result: connectorResult });
  }

  let pm: AgentOutput;
  try {
    trace.push({ step: "PortfolioManagerAgent makes final decision", agent: "PortfolioManagerAgent", status: "running", detail: "Weighing evidence, debate, and risk controls." });
    pm = await portfolioManagerAgent(task, research, debate, connectorResult);
    trace[trace.length - 1] = { step: "PortfolioManagerAgent makes final decision", agent: "PortfolioManagerAgent", status: "done", detail: pm };
  } catch (e: any) {
    trace[trace.length - 1] = { step: "PortfolioManagerAgent makes final decision", agent: "PortfolioManagerAgent", status: "error", detail: String(e.message || e) };
    return fail(502, "PortfolioManagerAgent failed. The MAS run stopped immediately.", { research, connector_decision: connectorDecision, selected_connector: selectedConnector, connector_result: connectorResult, debate });
  }

  return NextResponse.json({
    answer: pm.final_answer || "Trading MAS finished.",
    research,
    connector_decision: connectorDecision,
    selected_connector: selectedConnector,
    connector_result: connectorResult,
    debate,
    portfolio_manager: pm,
    trace,
    latency_ms: Date.now() - startedAt
  });
}
