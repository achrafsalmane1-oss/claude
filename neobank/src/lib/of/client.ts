import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { mockCall } from "./mock";

/**
 * Thin client for the OpenFinance (OF) MCP server.
 *
 * Configure via env:
 *   OPENFINANCE_MCP_URL   — Streamable-HTTP endpoint of the OF MCP server
 *   OPENFINANCE_MCP_TOKEN — optional bearer token
 *   OF_MOCK=1             — force mock mode even when a URL is set
 *
 * Without a URL the client serves realistic mock data so the app runs
 * out of the box.
 */

type OFClient = Client;

declare global {
  var __ofClient: Promise<OFClient> | undefined;
}

export function isMockMode(): boolean {
  return process.env.OF_MOCK === "1" || !process.env.OPENFINANCE_MCP_URL;
}

async function connect(): Promise<OFClient> {
  const url = process.env.OPENFINANCE_MCP_URL!;
  const token = process.env.OPENFINANCE_MCP_TOKEN;
  const transport = new StreamableHTTPClientTransport(new URL(url), {
    requestInit: token
      ? { headers: { Authorization: `Bearer ${token}` } }
      : undefined,
  });
  const client = new Client({ name: "neobank", version: "0.1.0" });
  await client.connect(transport);
  return client;
}

function getClient(): Promise<OFClient> {
  if (!globalThis.__ofClient) {
    globalThis.__ofClient = connect().catch((err) => {
      globalThis.__ofClient = undefined;
      throw err;
    });
  }
  return globalThis.__ofClient;
}

/**
 * Call an OF tool by its server-side name (e.g. "get_wallet_addresses",
 * "onchain_get_address_holdings") and return the parsed JSON payload.
 */
export async function callOF<T = unknown>(
  tool: string,
  args: Record<string, unknown> = {},
): Promise<T> {
  if (isMockMode()) {
    return mockCall(tool, args) as Promise<T>;
  }
  const client = await getClient();
  const result = await client.callTool({ name: tool, arguments: args });
  const content = (result.content ?? []) as Array<{
    type: string;
    text?: string;
  }>;
  const text = content
    .filter((c) => c.type === "text" && typeof c.text === "string")
    .map((c) => c.text)
    .join("\n");
  if (result.isError) {
    throw new Error(`OF tool ${tool} failed: ${text || "unknown error"}`);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as unknown as T;
  }
}
