export type Primitive = {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
  endpoint: string;
  examples: string[];
};

const fallback: Primitive[] = [
  {
    id: "stock",
    name: "StockPrimitive",
    description: "Lookup stock prices and market information.",
    capabilities: ["stock quote", "ticker lookup", "market data"],
    endpoint: "http://127.0.0.1:8001/invoke",
    examples: ["What is AAPL stock price?"]
  },
  {
    id: "news",
    name: "NewsPrimitive",
    description: "Search recent news and summarize current events.",
    capabilities: ["latest news", "recent events", "news retrieval"],
    endpoint: "http://127.0.0.1:8002/invoke",
    examples: ["latest news about climate change"]
  },
  {
    id: "amazon",
    name: "AmazonPrimitive",
    description: "Search Amazon product listings.",
    capabilities: ["amazon search", "product search", "shopping"],
    endpoint: "http://127.0.0.1:8003/invoke",
    examples: ["Search Amazon wireless earbuds"]
  },
  {
    id: "kiwi",
    name: "KiwiBookingPrimitive",
    description: "Search Kiwi flights and start a guided booking flow.",
    capabilities: ["flight search", "kiwi booking", "one-way flights", "round-trip flights"],
    endpoint: "http://127.0.0.1:8010/invoke",
    examples: ["Find a one-way flight from SEA to JFK on 2026-06-12 for 1 adult"]
  }
];

export function getRegistry(): Primitive[] {
  const raw = process.env.PRIMITIVE_REGISTRY_JSON;
  if (!raw) return fallback;
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return fallback;
    return parsed.map((p: any) => ({
      id: String(p.id),
      name: String(p.name),
      description: String(p.description || ""),
      capabilities: Array.isArray(p.capabilities) ? p.capabilities.map(String) : [],
      endpoint: String(p.endpoint),
      examples: Array.isArray(p.examples) ? p.examples.map(String) : []
    }));
  } catch {
    return fallback;
  }
}

export function publicRegistry() {
  return getRegistry().map(({ endpoint, ...safe }) => safe);
}
