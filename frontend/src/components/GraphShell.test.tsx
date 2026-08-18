// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { graphApi, type SessionPayload } from "../lib/apiClient";
import { AuthLanding } from "./GraphShell";

vi.mock("./landing/LandingOrbitField", () => ({
  LandingOrbitField: () => <div data-testid="landing-field" />,
}));

const guestSession: SessionPayload = {
  session_token: "guest-session-token",
  user_id: "guest-1234567890abcdef",
  display_name: "Guest Explorer",
  email: "",
  is_new_user: true,
};

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("AuthLanding guest entry", () => {
  it("enters the workspace with an isolated guest session", async () => {
    vi.spyOn(graphApi, "enterAsGuest").mockResolvedValue(guestSession);
    const authenticated = vi.fn();
    const enterWorkspace = vi.fn();

    render(
      <AuthLanding
        onAuthenticated={authenticated}
        onEnterWorkspace={enterWorkspace}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Enter the field/i }));
    await waitFor(() => expect(graphApi.enterAsGuest).toHaveBeenCalledTimes(1));
    expect(authenticated).toHaveBeenCalledWith(guestSession);
    expect(JSON.parse(localStorage.getItem("thoughtgraph:session") ?? "null")).toEqual(guestSession);
    await waitFor(() => expect(enterWorkspace).toHaveBeenCalledTimes(1), { timeout: 1200 });
  });

  it("keeps email sign-in available without creating a guest session", () => {
    const guestSpy = vi.spyOn(graphApi, "enterAsGuest");
    render(<AuthLanding onAuthenticated={() => undefined} onEnterWorkspace={() => undefined} />);

    fireEvent.click(screen.getByRole("button", { name: /Sign in with email/i }));

    expect(screen.getByRole("dialog", { name: /Enter your graph/i })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /Email address/i })).toBeInTheDocument();
    expect(guestSpy).not.toHaveBeenCalled();
  });

  it("keeps the landing visible while the Render backend is waking", async () => {
    vi.spyOn(graphApi, "enterAsGuest").mockImplementation(() => new Promise(() => undefined));
    const { container } = render(
      <AuthLanding onAuthenticated={() => undefined} onEnterWorkspace={() => undefined} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Enter the field/i }));

    expect(await screen.findByRole("button", { name: /Waking the field/i })).toBeDisabled();
    expect(screen.getByText(/See what your/i)).toBeInTheDocument();
    expect(container.querySelector(".auth-shell")).not.toHaveClass("is-entering");
  });

  it("falls back to email sign-in when guest preview is unavailable", async () => {
    vi.spyOn(graphApi, "enterAsGuest").mockRejectedValue(new Error("guest preview access is disabled"));
    render(<AuthLanding onAuthenticated={() => undefined} onEnterWorkspace={() => undefined} />);

    fireEvent.click(screen.getByRole("button", { name: /Enter the field/i }));

    expect(await screen.findByRole("dialog", { name: /Enter your graph/i })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("guest preview access is disabled");
  });
});
