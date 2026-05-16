"use client";

import { CodeBlockContainer } from "@/components/ai-elements/code-block";
import { applyMonacoTheme, getMonacoTheme } from "@/lib/monaco-theme";
import { toMonacoLanguage } from "@/lib/monaco-language";
import { cn } from "@/lib/utils";
import Editor, { type Monaco, type OnMount } from "@monaco-editor/react";
import { useControllableState } from "@radix-ui/react-use-controllable-state";
import { useTheme } from "next-themes";
import type { HTMLAttributes } from "react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
} from "react";
import type { editor } from "monaco-editor";
import type { BundledLanguage } from "shiki";

export { CodeBlockContainer };

interface CodeBlockEditorContextType {
  code: string;
  setCode: (code: string) => void;
}

const CodeBlockEditorContext = createContext<CodeBlockEditorContextType | null>(
  null
);

const DEFAULT_EDITOR_OPTIONS: editor.IStandaloneEditorConstructionOptions = {
  automaticLayout: true,
  folding: true,
  foldingHighlight: false,
  foldingStrategy: "indentation",
  showFoldingControls: "mouseover",
  fontFamily: "var(--font-mono), ui-monospace, monospace",
  fontLigatures: false,
  fontSize: 12,
  lineHeight: 18,
  lineNumbers: "off",
  minimap: { enabled: false },
  overviewRulerLanes: 0,
  hideCursorInOverviewRuler: true,
  scrollBeyondLastLine: false,
  wordWrap: "on",
  padding: { top: 16, bottom: 16 },
  renderLineHighlight: "none",
  selectionHighlight: false,
  occurrencesHighlight: "off",
  scrollbar: {
    verticalScrollbarSize: 8,
    horizontalScrollbarSize: 8,
  },
  guides: {
    bracketPairs: false,
    bracketPairsHorizontal: false,
    highlightActiveIndentation: false,
    indentation: false,
  },
  smoothScrolling: true,
  tabSize: 2,
};

type CodeBlockEditorProps = HTMLAttributes<HTMLDivElement> & {
  code: string;
  language: BundledLanguage | string;
  onCodeChange?: (code: string) => void;
  readOnly?: boolean;
  minHeight?: number;
  editorOptions?: editor.IStandaloneEditorConstructionOptions;
};

type CodeBlockEditorContentProps = {
  code: string;
  language: BundledLanguage | string;
  onCodeChange?: (code: string) => void;
  readOnly?: boolean;
  className?: string;
  minHeight?: number;
  editorOptions?: editor.IStandaloneEditorConstructionOptions;
};

function useIsDarkTheme() {
  const { resolvedTheme } = useTheme();
  return resolvedTheme === "dark";
}

const CodeBlockEditorBody = ({
  code,
  language,
  onCodeChange,
  readOnly = false,
  className,
  minHeight = 320,
  editorOptions,
}: CodeBlockEditorContentProps) => {
  const isDark = useIsDarkTheme();
  const monacoRef = useRef<Monaco | null>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const editorContext = useContext(CodeBlockEditorContext);

  const value = editorContext?.code ?? code;
  const onChange = editorContext?.setCode ?? onCodeChange;

  const monacoLanguage = useMemo(() => toMonacoLanguage(language), [language]);
  const theme = getMonacoTheme(isDark);

  const handleBeforeMount = useCallback((monaco: Monaco) => {
    monacoRef.current = monaco;
    applyMonacoTheme(monaco, isDark);
  }, [isDark]);

  const handleMount: OnMount = useCallback(
    (editorInstance, monaco) => {
      editorRef.current = editorInstance;
      monacoRef.current = monaco;
      applyMonacoTheme(monaco, isDark);
    },
    [isDark]
  );

  useEffect(() => {
    if (monacoRef.current) {
      applyMonacoTheme(monacoRef.current, isDark, true);
    }
  }, [isDark]);

  useEffect(() => {
    editorRef.current?.updateOptions({ readOnly });
  }, [readOnly]);

  const options = useMemo(
    () => ({
      ...DEFAULT_EDITOR_OPTIONS,
      ...editorOptions,
      readOnly,
    }),
    [editorOptions, readOnly]
  );

  return (
    <div
      className={cn(
        "relative min-h-0 flex-1 w-full overflow-hidden",
        className
      )}
      style={{ minHeight }}
    >
      <Editor
        beforeMount={handleBeforeMount}
        className="h-full [&_.monaco-editor]:outline-none"
        height="100%"
        key={theme}
        defaultLanguage={monacoLanguage}
        language={monacoLanguage}
        onChange={(next) => {
          if (!readOnly && onChange) {
            onChange(next ?? "");
          }
        }}
        onMount={handleMount}
        options={options}
        theme={theme}
        value={value}
      />
    </div>
  );
};

export const CodeBlockEditorContent = (props: CodeBlockEditorContentProps) => (
  <CodeBlockEditorBody {...props} />
);

export const CodeBlockEditor = ({
  code,
  language,
  onCodeChange,
  readOnly = false,
  minHeight = 320,
  editorOptions,
  className,
  ...props
}: CodeBlockEditorProps) => {
  const [editorCode, setEditorCode] = useControllableState({
    defaultProp: code,
    onChange: onCodeChange,
    prop: code,
  });

  const contextValue = useMemo(
    () => ({ code: editorCode, setCode: setEditorCode }),
    [editorCode, setEditorCode]
  );

  return (
    <CodeBlockEditorContext.Provider value={contextValue}>
      <CodeBlockContainer
        className={cn("flex min-h-0 flex-col", className)}
        language={language}
        {...props}
      >
        <CodeBlockEditorContent
          code={editorCode}
          editorOptions={editorOptions}
          language={language}
          minHeight={minHeight}
          onCodeChange={setEditorCode}
          readOnly={readOnly}
        />
      </CodeBlockContainer>
    </CodeBlockEditorContext.Provider>
  );
};
