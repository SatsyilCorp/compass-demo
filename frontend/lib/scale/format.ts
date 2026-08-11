export function formatCount(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

export function formatBytes(value: number): string {
  if (value < 1_000) return `${value} B`;
  if (value < 1_000_000) return `${(value / 1_000).toFixed(1)} KB`;
  if (value < 1_000_000_000) return `${(value / 1_000_000).toFixed(1)} MB`;
  return `${(value / 1_000_000_000).toFixed(2)} GB`;
}

export function formatDuration(value: number | null): string {
  if (value === null) return "Calculating";
  if (value < 60) return `${Math.max(0, Math.round(value))} sec`;
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return seconds === 0 ? `${minutes} min` : `${minutes} min ${seconds} sec`;
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: value < 1 ? 2 : 2,
    maximumFractionDigits: value < 1 ? 4 : 2,
  }).format(value);
}

export function formatPercent(value: number, maximumFractionDigits = 1): string {
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    maximumFractionDigits,
  }).format(value);
}
