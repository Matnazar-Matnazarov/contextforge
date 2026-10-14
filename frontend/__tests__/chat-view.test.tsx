import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ChatView } from "@/components/chat-view";
import { OrgContext } from "@/components/org-context";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));

const org = { id: "org-1", name: "Acme", role: "owner" as const, created_at: "" };
const json = (body: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));

function renderChat(conversationId: string | null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <OrgContext.Provider value={{ org, role: "owner" }}>
        <ChatView conversationId={conversationId} />
      </OrgContext.Provider>
    </QueryClientProvider>,
  );
}

const messages = [
  { id: "m1", role: "user", content: "How many leave days?", insufficient_context: false, citations: [], created_at: "" },
  {
    id: "m2", role: "assistant", content: "25 days.", insufficient_context: false, created_at: "",
    citations: [{ id: "c1", document_id: "d1", document_title: "policy.md", chunk_id: "d1:0", source_label: "S1", page_number: 2, section: "", excerpt: "25 days of paid leave" }],
  },
  { id: "m3", role: "assistant", content: "I couldn't find enough information.", insufficient_context: true, citations: [], created_at: "" },
];

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

describe("ChatView", () => {
  it("shows history, citations and opens the source panel with the excerpt", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json(messages)));
    renderChat("conv-1");
    expect(await screen.findByText("25 days.")).toBeInTheDocument();
    expect(screen.getByText("Not enough information")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /S1.*policy\.md/ }));
    expect(screen.getAllByText("25 days of paid leave").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /Download original/ })[0]).toHaveAttribute("href", "/api/orgs/org-1/documents/d1/download/");
  });

  it("shows a loading state while waiting and an error state when the API fails", async () => {
    document.cookie = "csrftoken=t";
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") return json({ error: { code: "llm_unavailable", message: "The answer service is temporarily unavailable." } }, 502);
      return json([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderChat("conv-1");
    await userEvent.type(await screen.findByLabelText("Your question"), "What is the policy?");
    await userEvent.click(screen.getByRole("button", { name: "Send question" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("temporarily unavailable");
    await waitFor(() => expect(screen.queryByText(/Searching documents/)).not.toBeInTheDocument());
  });

  it("validates empty questions client-side", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json([])));
    renderChat("conv-1");
    await userEvent.click(await screen.findByRole("button", { name: "Send question" }));
    expect(await screen.findByText("Type a question")).toBeInTheDocument();
  });
});
