export class ScaleAdapterError extends Error {
  status: number;
  body: Record<string, unknown>;

  constructor(status: number, body: Record<string, unknown>, message?: string) {
    super(message ?? String(body.error ?? `scale_error_${status}`));
    this.name = "ScaleAdapterError";
    this.status = status;
    this.body = body;
  }
}

export function scaleErrorMessage(error: unknown): string {
  if (error instanceof ScaleAdapterError) {
    const detail = error.body.message;
    return typeof detail === "string" ? detail : error.message;
  }
  if (error instanceof Error) return error.message;
  return "The scale service returned an unexpected response.";
}
