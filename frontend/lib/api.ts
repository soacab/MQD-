const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export async function fetchHealth(): Promise<{ status: string; reachable: boolean }> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
    if (!response.ok) {
      return { status: `HTTP ${response.status}`, reachable: false };
    }
    const data = (await response.json()) as { status?: string };
    return { status: data.status || "unknown", reachable: data.status === "ok" };
  } catch {
    return { status: "unreachable", reachable: false };
  }
}
