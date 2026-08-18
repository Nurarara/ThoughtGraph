// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { graphApi } from "../lib/apiClient";
import { DEMO_SESSION } from "../lib/demoWorkspace";
import { AuthLanding, GraphShell } from "./GraphShell";

vi.mock("./landing/LandingOrbitField", () => ({
  LandingOrbitField: () => <div data-testid="landing-field" />,
}));

vi.mock("./GraphCanvas", () => ({
  GraphCanvas: ({ graph }: { graph: { nodes: unknown[] } | null }) => (
    <div data-testid="graph-canvas">{graph?.nodes.length ?? 0} demo nodes</div>
  ),
}));

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("AuthLanding demo entry", () => {
  it("enters the browser-local workspace without contacting the backend", async () => {
    const authenticated = vi.fn();
    const enterWorkspace = vi.fn();

    render(
      <AuthLanding
        onAuthenticated={authenticated}
        onEnterWorkspace={enterWorkspace}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Enter the field/i }));
    expect(authenticated).toHaveBeenCalledWith(DEMO_SESSION);
    expect(JSON.parse(localStorage.getItem("thoughtgraph:session") ?? "null")).toEqual(DEMO_SESSION);
    await waitFor(() => expect(enterWorkspace).toHaveBeenCalledTimes(1), { timeout: 1200 });
  });

  it("keeps email sign-in available without creating a guest session", () => {
    render(<AuthLanding onAuthenticated={() => undefined} onEnterWorkspace={() => undefined} />);

    fireEvent.click(screen.getByRole("button", { name: /Sign in with email/i }));

    expect(screen.getByRole("dialog", { name: /Enter your graph/i })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /Email address/i })).toBeInTheDocument();
  });

  it("loads the sample graph locally after entry", async () => {
    const getGraph = vi.spyOn(graphApi, "getGraph");
    const getMe = vi.spyOn(graphApi, "getMe");
    const enterWorkspace = vi.fn();
    const view = render(<GraphShell showLanding onEnterWorkspace={enterWorkspace} />);

    fireEvent.click(screen.getByRole("button", { name: /Enter the field/i }));
    await waitFor(() => expect(enterWorkspace).toHaveBeenCalledTimes(1), { timeout: 1200 });
    view.rerender(<GraphShell showLanding={false} onEnterWorkspace={enterWorkspace} />);

    expect(await screen.findByTestId("graph-canvas")).toHaveTextContent("9 demo nodes");
    expect(screen.getByText(/interactive demo/i)).toBeInTheDocument();
    expect(getGraph).not.toHaveBeenCalled();
    expect(getMe).not.toHaveBeenCalled();
  });
});
