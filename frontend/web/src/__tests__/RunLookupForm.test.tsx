const mockPush = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

import { render, screen, fireEvent } from "@testing-library/react";

import { RunLookupForm } from "@/components/runs/RunLookupForm";

afterEach(() => jest.clearAllMocks());

it("navigates to the run trace page on submit", () => {
  render(<RunLookupForm />);

  fireEvent.change(screen.getByLabelText("Request id"), {
    target: { value: "  req-99  " },
  });
  fireEvent.click(screen.getByText("View trace"));

  expect(mockPush).toHaveBeenCalledWith("/runs/req-99");
});

it("disables submit and does not navigate when the input is empty", () => {
  render(<RunLookupForm />);

  const button = screen.getByText("View trace") as HTMLButtonElement;
  expect(button.disabled).toBe(true);

  // submitting the form directly with a blank id is a no-op
  fireEvent.submit(button.closest("form")!);
  expect(mockPush).not.toHaveBeenCalled();
});

it("url-encodes the request id", () => {
  render(<RunLookupForm />);

  fireEvent.change(screen.getByLabelText("Request id"), {
    target: { value: "a/b c" },
  });
  fireEvent.click(screen.getByText("View trace"));

  expect(mockPush).toHaveBeenCalledWith("/runs/a%2Fb%20c");
});
