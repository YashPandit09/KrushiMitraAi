export type Theme = "light" | "dark";
const KEY = "krushimitra-theme";

export function storedTheme(): Theme | undefined {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : undefined;
  } catch {
    return undefined; // storage blocked (private mode, strict settings)
  }
}

export function currentTheme(): Theme {
  const stamped = document.documentElement.dataset.theme;
  if (stamped === "light" || stamped === "dark") return stamped;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(theme: Theme | undefined): void {
  if (theme) document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
}

export function saveTheme(theme: Theme): void {
  applyTheme(theme);
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* non-essential */
  }
}
