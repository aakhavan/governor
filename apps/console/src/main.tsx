import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { installEventSource } from "./api/eventSource";
import { App } from "./App";
import "./styles.css";

installEventSource();

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
