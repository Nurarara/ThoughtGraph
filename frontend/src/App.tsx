import { useState } from "react";

import { GraphShell } from "./components/GraphShell";
import { LandingPage } from "./components/landing/LandingPage";
import { loadSession } from "./lib/apiClient";

export default function App() {
  const [entered, setEntered] = useState(() => Boolean(loadSession()) || new URLSearchParams(window.location.search).has("token"));

  if (!entered) {
    return <LandingPage onCreateUniverse={() => setEntered(true)} />;
  }

  return <GraphShell />;
}
