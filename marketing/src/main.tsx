import { StrictMode } from "react"
import { createRoot, hydrateRoot } from "react-dom/client"

import "./index.css"
import App from "./App.tsx"

const container = document.getElementById("root")
if (!container) {
  throw new Error("Landing root is missing")
}

const application = (
  <StrictMode>
    <App />
  </StrictMode>
)

if (container.hasChildNodes()) {
  hydrateRoot(container, application)
} else {
  createRoot(container).render(application)
}
