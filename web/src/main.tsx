import { createRoot } from "react-dom/client";
import App from "./App";
import "./theme.css";

import { startReplay } from "./replay";

// On the hosted site, API calls are answered from a recorded run; locally this is a no-op.
startReplay().finally(() => createRoot(document.getElementById("root")!).render(<App />));
