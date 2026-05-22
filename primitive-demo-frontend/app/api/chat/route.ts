import { NextResponse } from "next/server";
import { getRegistry } from "../../lib/registry";

type RouteDecision = {
  use_tool: boolean;
  tool_name?: string | null;
  tool_id?: string | null;
  args?: Record<string, any>;
  direct_response?: string;
  reason?: string;
};

async function askQwen(query: string): Promise<RouteDecision> {
  const registry = getRegistry();
  const toolList = registry.map(t => ({ id: t.id, name: t.name, description: t.description, capabilities: t.capabilities, examples: t.examples }));
  const prompt = `You are a tool router for a Primitive-as-a-Service demo.\nAvailable tools:\n${JSON.stringify(toolList, null, 2)}\n\nDecide whether the user query needs a tool. Return ONLY valid JSON, no markdown.\nSchema:\n{\n  "use_tool": true or false,\n  "tool_id": "one available tool id or null",\n  "tool_name": "tool name or null",\n  "args": {"query": "original user query", "...": "extracted arguments if obvious"},\n  "direct_response": "answer directly if no tool is needed",\n  "reason": "brief reason"\n}\n\nUser query: ${query}`;

  const base = process.env.OLLAMA_BASE_URL || "http://127.0.0.1:11434";
  const model = process.env.OLLAMA_MODEL || "qwen3:8b";
  const res = await fetch(`${base}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, prompt, stream: false, options: { temperature: 0 } })
  });
  if (!res.ok) throw new Error(`Ollama router failed: ${res.status}`);
  const data = await res.json();
  const text = String(data.response || "").replace(/```json|```/g, "").trim();
  const match = text.match(/\{[\s\S]*\}/);
  if (!match) throw new Error("Router did not return JSON");
  return JSON.parse(match[0]);
}

function fallbackRouter(query: string): RouteDecision {
  const q = query.toLowerCase();
  if (/(stock|share|price|ticker|aapl|tsla|nvda|msft)/.test(q)) return { use_tool: true, tool_id: "stock", tool_name: "StockPrimitive", args: { query }, reason: "The query asks for market data." };
  if (/(flight|fly|airport|booking|kiwi|one-way|roundtrip|round-trip|ticket|airline|sea|jfk|ord|lax|sfo)/.test(q)) return { use_tool: true, tool_id: "kiwi", tool_name: "KiwiBookingPrimitive", args: { query }, reason: "The query asks for flight search or booking." };
  if (/(amazon|product|buy|shopping|earbuds|laptop|headphones)/.test(q)) return { use_tool: true, tool_id: "amazon", tool_name: "AmazonPrimitive", args: { query }, reason: "The query asks for product search." };
  if (/(search|latest|recent|news|find)/.test(q)) return { use_tool: true, tool_id: "news", tool_name: "NewsPrimitive", args: { query }, reason: "The query asks for news retrieval." };
  return { use_tool: false, direct_response: "This does not seem to require an external primitive. I can answer directly in the product demo.", reason: "No external tool is necessary." };
}

export async function POST(req: Request) {
  const startedAt = Date.now();
  const body = await req.json();
  const query = String(body.query || "").trim();
  const trace: any[] = [];
  if (!query) return NextResponse.json({ error: "Missing query" }, { status: 400 });

  trace.push({ step: "Receive user query", status: "done", detail: query });

  let decision: RouteDecision;
  try {
    decision = await askQwen(query);
    trace.push({ step: "Qwen router decision", status: "done", detail: decision });
  } catch (e: any) {
    decision = fallbackRouter(query);
    trace.push({ step: "Qwen router decision", status: "fallback", detail: String(e.message || e) });
    trace.push({ step: "Fallback router decision", status: "done", detail: decision });
  }

  if (!decision.use_tool) {
    return NextResponse.json({ answer: decision.direct_response || "No tool call needed.", decision, trace, latency_ms: Date.now() - startedAt });
  }

  const registry = getRegistry();
  const primitive = registry.find(t => t.id === decision.tool_id || t.name === decision.tool_name);
  if (!primitive) {
    trace.push({ step: "Primitive registry lookup", status: "error", detail: "No matching primitive found." });
    return NextResponse.json({ answer: "The router selected a tool that is not registered.", decision, trace }, { status: 500 });
  }

  trace.push({ step: "Primitive registry lookup", status: "done", detail: { selected: primitive.name } });
  trace.push({ step: "Invoke primitive", status: "running", detail: { selected: primitive.name } });

  try {
    const invoke = await fetch(primitive.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, ...(decision.args || {}) })
    });
    const primitiveResult = await invoke.json().catch(() => ({}));
    trace[trace.length - 1] = { step: "Invoke primitive", status: invoke.ok ? "done" : "error", detail: { selected: primitive.name, status: invoke.status } };
    trace.push({ step: "Return final answer", status: "done", detail: "Primitive result returned to chat UI." });
    return NextResponse.json({ answer: primitiveResult.answer || primitiveResult.result || JSON.stringify(primitiveResult, null, 2), decision, selected_tool: { id: primitive.id, name: primitive.name }, primitive_result: primitiveResult, trace, latency_ms: Date.now() - startedAt });
  } catch (e: any) {
    trace[trace.length - 1] = { step: "Invoke primitive", status: "error", detail: String(e.message || e) };
    return NextResponse.json({ answer: `Selected ${primitive.name}, but invocation failed.`, decision, selected_tool: { id: primitive.id, name: primitive.name }, trace, latency_ms: Date.now() - startedAt }, { status: 502 });
  }
}
