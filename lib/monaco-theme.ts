import type { Monaco } from "@monaco-editor/react";

const THEME_LIGHT = "expression-light";
const THEME_DARK = "expression-dark";

const FALLBACK = {
  light: {
    background: "#ffffff",
    foreground: "#252525",
    muted: "#737373",
  },
  dark: {
    background: "#000000",
    foreground: "#fafafa",
    muted: "#a3a3a3",
  },
} as const;

let themesRegistered = false;

/** Monaco only accepts #hex or rgb()/rgba() — not lab()/oklch() strings directly. */
function cssColorToHex(color: string, fallback: string): string {
  if (!color || color === "transparent") return fallback;

  const canvas = document.createElement("canvas");
  canvas.width = 1;
  canvas.height = 1;
  const ctx = canvas.getContext("2d");
  if (!ctx) return fallback;

  try {
    ctx.fillStyle = fallback;
    ctx.fillStyle = color;
    const normalized = ctx.fillStyle;

    if (normalized.startsWith("#")) {
      return normalized.length === 4
        ? `#${normalized[1]}${normalized[1]}${normalized[2]}${normalized[2]}${normalized[3]}${normalized[3]}`
        : normalized.slice(0, 7);
    }

    const match = normalized.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (match) {
      const [, r, g, b] = match;
      return `#${[r, g, b]
        .map((n) => Number(n).toString(16).padStart(2, "0"))
        .join("")}`;
    }
  } catch {
    // canvas cannot parse this color format
  }

  return fallback;
}

function readCssVarFromHost(
  host: HTMLElement,
  varName: string,
  kind: "background" | "foreground",
  fallback: string
): string {
  const probe = document.createElement("span");
  if (kind === "background") {
    probe.style.backgroundColor = `var(${varName})`;
  } else {
    probe.style.color = `var(${varName})`;
  }
  host.appendChild(probe);
  const style = getComputedStyle(probe);
  const raw = kind === "background" ? style.backgroundColor : style.color;
  host.removeChild(probe);
  return cssColorToHex(raw, fallback);
}

/** Sample palette inside an isolated host — never toggles `html.dark`. */
function readPalette(mode: "light" | "dark") {
  const fallbacks = FALLBACK[mode];
  const host = document.createElement("div");
  host.style.cssText =
    "position:absolute;visibility:hidden;pointer-events:none;width:0;height:0;overflow:hidden;";
  if (mode === "dark") {
    host.classList.add("dark");
  }
  document.body.appendChild(host);

  const palette = {
    background: readCssVarFromHost(
      host,
      "--background",
      "background",
      fallbacks.background
    ),
    foreground: readCssVarFromHost(
      host,
      "--foreground",
      "foreground",
      fallbacks.foreground
    ),
    muted: readCssVarFromHost(
      host,
      "--muted-foreground",
      "foreground",
      fallbacks.muted
    ),
  };

  document.body.removeChild(host);
  return palette;
}

/** GitHub-style themes aligned with Shiki github-light / github-dark. */
export function registerMonacoThemes(monaco: Monaco, force = false) {
  if (themesRegistered && !force) return;

  const light = readPalette("light");
  const dark = readPalette("dark");

  const shared = {
    "editor.lineHighlightBackground": "#00000000",
    "editor.lineHighlightBorder": "#00000000",
  };

  monaco.editor.defineTheme(THEME_LIGHT, {
    base: "vs",
    inherit: true,
    rules: [],
    colors: {
      ...shared,
      "editor.background": light.background,
      "editor.foreground": light.foreground,
      "editorLineNumber.foreground": light.muted,
      "editorGutter.background": light.background,
    },
  });

  monaco.editor.defineTheme(THEME_DARK, {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {
      ...shared,
      "editor.background": dark.background,
      "editor.foreground": dark.foreground,
      "editorLineNumber.foreground": dark.muted,
      "editorGutter.background": dark.background,
    },
  });

  themesRegistered = true;
}

export function applyMonacoTheme(
  monaco: Monaco,
  isDark: boolean,
  reRegister = false
) {
  registerMonacoThemes(monaco, reRegister);
  monaco.editor.setTheme(getMonacoTheme(isDark));
}

export function getMonacoTheme(isDark: boolean) {
  return isDark ? THEME_DARK : THEME_LIGHT;
}
