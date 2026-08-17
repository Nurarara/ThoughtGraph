import { useCallback, useEffect, useState } from "react";

import { GraphShell } from "./components/GraphShell";

function shouldOpenWorkspace() {
  return window.location.pathname.startsWith("/app")
    || new URLSearchParams(window.location.search).has("token");
}

export default function App() {
  const [workspaceOpen, setWorkspaceOpen] = useState(shouldOpenWorkspace);

  useEffect(() => {
    const syncRoute = () => setWorkspaceOpen(shouldOpenWorkspace());
    window.addEventListener("popstate", syncRoute);
    return () => window.removeEventListener("popstate", syncRoute);
  }, []);

  const enterWorkspace = useCallback(() => {
    window.history.pushState({}, document.title, "/app");
    setWorkspaceOpen(true);
  }, []);

  return <GraphShell showLanding={!workspaceOpen} onEnterWorkspace={enterWorkspace} />;
}
