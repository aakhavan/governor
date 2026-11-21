import { BrowserRouter, Route, Routes } from "react-router-dom";
import { GraphPage } from "./pages/GraphPage";
import { RunPage } from "./pages/RunPage";
import { RunsPage } from "./pages/RunsPage";
import { Shell } from "./shell/Shell";
import { ThemeProvider } from "./theme";

export function App() {
  return (
    <ThemeProvider>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Shell>
          <Routes>
            <Route path="/" element={<RunsPage />} />
            <Route path="/runs/:runId" element={<RunPage />} />
            <Route path="/graphs/:graph" element={<GraphPage />} />
          </Routes>
        </Shell>
      </BrowserRouter>
    </ThemeProvider>
  );
}
