export function currency(value: number | null | undefined, decimals = 0): string {
  if (value == null || !isFinite(value)) return "—";
  const abs = Math.abs(value);
  const formatted = abs.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return `${value < 0 ? "-" : ""}$${formatted}`;
}

export function pct(value: number | null | undefined, decimals = 1): string {
  if (value == null || !isFinite(value)) return "—";
  return `${(value * 100).toFixed(decimals)}%`;
}

export function num(value: number | null | undefined, decimals = 2): string {
  if (value == null || !isFinite(value)) return "—";
  return value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
