const mockRegisterOTel = jest.fn();

jest.mock("@vercel/otel", () => ({
  registerOTel: mockRegisterOTel,
}));

import { register } from "@/instrumentation";

afterEach(() => {
  jest.clearAllMocks();
  delete process.env.OTEL_SERVICE_NAME;
});

it("registers OTel with the default service name", () => {
  register();
  expect(mockRegisterOTel).toHaveBeenCalledWith({ serviceName: "frontend-hitl-ui" });
});

it("honours OTEL_SERVICE_NAME when set", () => {
  process.env.OTEL_SERVICE_NAME = "custom-ui";
  register();
  expect(mockRegisterOTel).toHaveBeenCalledWith({ serviceName: "custom-ui" });
});
