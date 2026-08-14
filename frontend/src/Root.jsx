import { useCallback, useEffect, useState } from "react";
import App from "./App.jsx";
import Landing from "./components/Landing.jsx";

function viewFromHash() {
  return window.location.hash === "#demo" ? "demo" : "landing";
}

export default function Root() {
  const [view, setView] = useState(viewFromHash);

  useEffect(() => {
    const onHashChange = () => setView(viewFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const launchDemo = useCallback(() => {
    window.location.hash = "#demo";
    setView("demo");
  }, []);

  const backToLanding = useCallback(() => {
    window.location.hash = "";
    setView("landing");
  }, []);

  if (view === "demo") return <App onBackToLanding={backToLanding} />;
  return <Landing onLaunch={launchDemo} />;
}
