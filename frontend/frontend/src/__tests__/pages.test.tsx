import { render, screen } from "@testing-library/react";

import HomePage from "@/app/page";
import RootLayout from "@/app/layout";

describe("HomePage", () => {
  it("renders the HITL queue navigation link", () => {
    render(<HomePage />);
    const link = screen.getByRole("link", { name: "HITL Approval Queue" });
    expect(link).toHaveAttribute("href", "/hitl");
  });
});

describe("RootLayout", () => {
  it("renders its children", () => {
    // RootLayout returns <html><body>…</body></html>; rendered inside the jsdom container this
    // nests html (React warns about DOM nesting) but still mounts the children — enough to cover it.
    render(
      <RootLayout>
        <div>child-content</div>
      </RootLayout>,
    );
    expect(screen.getByText("child-content")).toBeInTheDocument();
  });
});
