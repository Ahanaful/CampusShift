const base = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");
let accessToken = null;
let onUnauthorized = () => {};

export function setSession(token, unauthorized = () => {}) {
  accessToken = token;
  onUnauthorized = unauthorized;
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export async function api(path, { body, signal, ...options } = {}) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  const timeout = setTimeout(abort, 10000);
  try {
    const response = await fetch(`${base}/api${path}`, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    if (response.status === 204) return null;
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      if (response.status === 401 && accessToken) onUnauthorized();
      const detail = data?.detail;
      const message = Array.isArray(detail)
        ? detail.map((error) => `${error.loc.at(-1)}: ${error.msg}`).join(". ")
        : typeof detail === "string"
          ? detail
          : "The request could not be completed.";
      throw new ApiError(message, response.status);
    }
    if (data === null)
      throw new Error("The API returned an unexpected response.");
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error.name === "AbortError") throw error;
    throw new Error(
      "Cannot reach CampusShift. Check that the backend is running and try again.",
    );
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", abort);
  }
}
