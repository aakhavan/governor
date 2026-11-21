import { useEffect, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { copy } from "../copy";
import { Mark } from "../graph/icons";
import { useTheme } from "../theme";

export function Shell({ children }: { children: ReactNode }) {
  const { theme, toggle } = useTheme();
  useEffect(() => {
    document.title = copy.appName;
  }, []);

  return (
    <div className="app">
      <a className="skip" href="#main">
        {copy.skip}
      </a>
      <aside className="nav">
        <div className="brand">
          <Mark />
          <span>{copy.appName}</span>
        </div>
        <nav aria-label={copy.navLabel}>
          <NavLink to="/" end>
            {copy.navRuns}
          </NavLink>
          <NavLink to="/graphs/build">{copy.navBuild}</NavLink>
          <NavLink to="/graphs/ask">{copy.navAsk}</NavLink>
        </nav>
      </aside>
      <header className="topbar">
        <p className="tagline">{copy.tagline}</p>
        <button type="button" className="theme-toggle" onClick={toggle}>
          {theme === "dark" ? copy.themeToLight : copy.themeToDark}
        </button>
      </header>
      <main id="main" className="main">
        {children}
      </main>
    </div>
  );
}
