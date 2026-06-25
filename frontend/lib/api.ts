import type { ValidationResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

export async function validate(
  tradesFile: File,
  barsFile: File | null,
  opts: { seed?: number; mcIterations?: number } = {},
): Promise<ValidationResponse> {
  const form = new FormData();
  form.append("trades", tradesFile);
  if (barsFile) form.append("bars", barsFile);
  if (opts.seed !== undefined) form.append("seed", String(opts.seed));
  if (opts.mcIterations !== undefined) form.append("mc_iterations", String(opts.mcIterations));

  const res = await fetch(`${API_BASE}/api/validate`, { method: "POST", body: form });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore parse errors */
    }
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<ValidationResponse>;
}
