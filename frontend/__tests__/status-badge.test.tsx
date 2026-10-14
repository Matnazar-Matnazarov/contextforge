import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "@/components/status-badge";

describe("StatusBadge", () => {
  it.each([
    ["pending", "Pending"],
    ["processing", "Processing"],
    ["indexed", "Indexed"],
    ["failed", "Failed"],
  ] as const)("renders %s", (status, label) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
