import {
  reportWebVital,
  serializeWebVital,
  type WebVitalMetric,
} from "@/lib/observability/web-vitals";

const metric: WebVitalMetric = {
  name: "LCP",
  value: 1234.5,
  id: "v1-abc",
  rating: "good",
  navigationType: "navigate",
};

describe("serializeWebVital", () => {
  it("includes only the non-PII metric fields", () => {
    const parsed = JSON.parse(serializeWebVital(metric));
    expect(parsed).toEqual({
      name: "LCP",
      value: 1234.5,
      id: "v1-abc",
      rating: "good",
      navigationType: "navigate",
    });
  });

  it("normalises missing optional fields to null", () => {
    const parsed = JSON.parse(serializeWebVital({ name: "CLS", value: 0.01, id: "x" }));
    expect(parsed.rating).toBeNull();
    expect(parsed.navigationType).toBeNull();
  });
});

describe("reportWebVital", () => {
  const originalSendBeacon = navigator.sendBeacon;

  afterEach(() => {
    navigator.sendBeacon = originalSendBeacon;
    jest.restoreAllMocks();
  });

  it("is a no-op when no endpoint is configured", () => {
    const beacon = jest.fn().mockReturnValue(true);
    navigator.sendBeacon = beacon;
    expect(reportWebVital(metric, undefined)).toBe(false);
    expect(beacon).not.toHaveBeenCalled();
  });

  it("sends the metric via sendBeacon when an endpoint is set", () => {
    const beacon = jest.fn().mockReturnValue(true);
    navigator.sendBeacon = beacon;
    const result = reportWebVital(metric, "/api/web-vitals");
    expect(result).toBe(true);
    expect(beacon).toHaveBeenCalledWith("/api/web-vitals", serializeWebVital(metric));
  });

  it("falls back to fetch keepalive when sendBeacon is unavailable", () => {
    // @ts-expect-error — simulate an environment without sendBeacon
    navigator.sendBeacon = undefined;
    const fetchMock = jest.fn().mockResolvedValue(undefined);
    global.fetch = fetchMock as unknown as typeof fetch;
    const result = reportWebVital(metric, "/api/web-vitals");
    expect(result).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web-vitals",
      expect.objectContaining({ method: "POST", keepalive: true }),
    );
  });
});
