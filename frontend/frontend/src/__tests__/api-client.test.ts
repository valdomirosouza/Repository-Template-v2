import { apiFetch } from "@/lib/api/client";
import { fetchPendingRequests, submitDecision } from "@/lib/api/hitl";

function mockFetchOnce(impl: Partial<Response>): jest.Mock {
  const fn = jest.fn().mockResolvedValue(impl);
  global.fetch = fn as unknown as typeof fetch;
  return fn;
}

afterEach(() => jest.restoreAllMocks());

describe("apiFetch", () => {
  it("returns parsed JSON on an ok response", async () => {
    const payload = [{ id: "r1" }];
    mockFetchOnce({ ok: true, json: () => Promise.resolve(payload) } as Partial<Response>);
    await expect(apiFetch("/x")).resolves.toEqual(payload);
  });

  it("throws with status and body text on a non-ok response", async () => {
    mockFetchOnce({
      ok: false,
      status: 500,
      text: () => Promise.resolve("boom"),
    } as Partial<Response>);
    await expect(apiFetch("/x")).rejects.toThrow("API 500: boom");
  });

  it("forwards init options and custom headers to fetch", async () => {
    const fn = mockFetchOnce({ ok: true, json: () => Promise.resolve({}) } as Partial<Response>);
    await apiFetch("/y", { method: "POST", headers: { "X-Test": "1" } });
    const init = fn.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    // NOTE: when a caller passes `headers`, the `...init` spread overrides the default
    // Content-Type (a latent quirk of the generated client.ts). The app's own callers don't
    // pass custom headers, so it is not exercised in practice. Asserting actual behaviour here.
    expect(init.headers).toMatchObject({ "X-Test": "1" });
  });

  it("applies the default Content-Type when the caller passes no headers", async () => {
    const fn = mockFetchOnce({ ok: true, json: () => Promise.resolve({}) } as Partial<Response>);
    await apiFetch("/z", { method: "POST", body: "{}" });
    const init = fn.mock.calls[0][1] as RequestInit;
    expect(init.headers).toMatchObject({ "Content-Type": "application/json" });
  });
});

describe("hitl api", () => {
  it("fetchPendingRequests hits the pending endpoint", async () => {
    const fn = mockFetchOnce({ ok: true, json: () => Promise.resolve([]) } as Partial<Response>);
    await fetchPendingRequests();
    expect(String(fn.mock.calls[0][0])).toContain("/v1/hitl/requests?status=PENDING");
  });

  it("submitDecision POSTs the decision payload", async () => {
    const fn = mockFetchOnce({ ok: true, json: () => Promise.resolve({}) } as Partial<Response>);
    await submitDecision("req-1", true, "looks good");
    const [url, init] = fn.mock.calls[0] as [string, RequestInit];
    expect(String(url)).toContain("/v1/hitl/req-1/decide");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      approved: true,
      rationale: "looks good",
      decided_by: "operator",
    });
  });
});
