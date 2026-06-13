const mockReportWebVital = jest.fn();
const sampleMetric = { name: "LCP", value: 1234, id: "v1-abc" };

jest.mock("@/lib/observability/web-vitals", () => ({
  reportWebVital: mockReportWebVital,
}));
// Invoke the hook callback synchronously with a sample metric so the wiring is exercised.
jest.mock("next/web-vitals", () => ({
  useReportWebVitals: (cb: (m: unknown) => void) => cb(sampleMetric),
}));

import { render } from "@testing-library/react";

import { WebVitals } from "@/components/observability/WebVitals";

afterEach(() => jest.clearAllMocks());

it("renders nothing and forwards the metric to the reporter", () => {
  const { container } = render(<WebVitals />);
  expect(container).toBeEmptyDOMElement();
  expect(mockReportWebVital).toHaveBeenCalledWith(sampleMetric);
});
