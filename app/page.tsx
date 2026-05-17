"use client"

import { useEffect, useRef, useState } from "react"
import { Waitlist } from "@clerk/nextjs"
import {
  ArrowRight,
  ChartLineUp,
  Code,
  Detective,
  GitDiff,
  MicrosoftExcelLogo,
  Robot,
  Sparkle,
  Terminal,
} from "@phosphor-icons/react"
import { motion } from "motion/react"

import { Logo } from "@/components/logo"

const FEATURE_WORDS = [
  "express your model",
  "excel for agents",
  "your models, alive",
  "model as code",
  "lovable for models",
  "agent that knows math",
  "helps you model"
]

const FEATURES = [
  {
    icon: Code,
    title: "Models as code",
    description:
      "Write Excel-like rows as Python functions. The framework builds the DAG, resolves dependencies, and solves in topological order — no graph wiring needed.",
  },
  {
    icon: MicrosoftExcelLogo,
    title: "Excel import & export",
    description:
      "Round-trip any .xlsx file. The importer converts formula bands into clean Python rows; the exporter writes formulas back and verifies every cell matches.",
  },
  {
    icon: ChartLineUp,
    title: "xl.* function library",
    description:
      "NPV, IRR, XIRR, VLOOKUP, cumsum, running_max — the full Excel financial toolkit, callable from any row or scalar without leaving Python.",
  },
  {
    icon: Robot,
    title: "Agent loop",
    description:
      "Claude iterates on your model: one change at a time, run → diff → commit. Skills keep it disciplined — bottom-up, override-aware, Excel-faithful.",
  },
  {
    icon: GitDiff,
    title: "Snapshots & diff",
    description:
      "Every solve is compared to the committed snapshot. Cell-level drift surfaces immediately. CI gates merges when numbers move unexpectedly.",
  },
  {
    icon: Detective,
    title: "Override discipline",
    description:
      "Hardcoded adjustments live in overrides.toml — never baked into formulas. Every override carries a reason, author, and period.",
  },
]

function useWordCycling(baseText: string, featureWords: string[]) {
  const [currentText, setCurrentText] = useState(baseText)
  const featureIndexRef = useRef(0)
  const isBaseRef = useRef(true)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    function schedule() {
      const delay = isBaseRef.current ? 5000 : 10000
      timerRef.current = setTimeout(() => {
        if (isBaseRef.current) {
          setCurrentText(featureWords[featureIndexRef.current % featureWords.length])
          featureIndexRef.current++
          isBaseRef.current = false
        } else {
          setCurrentText(baseText)
          isBaseRef.current = true
        }
        schedule()
      }, delay)
    }
    schedule()
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return currentText
}

export default function HomePage() {
  const logoText = useWordCycling("expression", FEATURE_WORDS)

  return (
    <div className="relative bg-background">
      {/* subtle grid background */}
      <div
        className="pointer-events-none fixed inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(to right, currentColor 1px, transparent 1px), linear-gradient(to bottom, currentColor 1px, transparent 1px)",
          backgroundSize: "64px 24px",
        }}
      />

      {/* nav */}
      <header className="relative z-10 flex items-center justify-between px-8 py-6">
        <Logo text="expression" />
        <a
          href="/expr"
          className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          Start Modelling <ArrowRight size={14} />
        </a>
      </header>

      {/* hero */}
      <section className="relative z-10 flex flex-col items-center px-6 pt-16 pb-16 text-center">
        <motion.div
          animate={{ opacity: 1, y: 0 }}
          className="mb-8 inline-flex items-center gap-2 rounded-full border border-border bg-muted/60 px-3 py-1 text-xs text-muted-foreground"
          initial={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.4 }}
        >
          <Sparkle size={12} weight="fill" />
          Early access — join the waitlist
        </motion.div>

        <motion.div
          animate={{ opacity: 1, y: 0 }}
          className="mb-6"
          initial={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.5, delay: 0.05 }}
        >
          <div className="flex justify-center" style={{ zoom: 4 }}>
            <Logo
              max={900}
              min={200}
              spacing="-0.06em"
              text={logoText}
            />
          </div>
        </motion.div>

        <motion.p
          animate={{ opacity: 1, y: 0 }}
          className="mb-3 max-w-lg text-lg text-muted-foreground"
          initial={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.5, delay: 0.12 }}
        >
          You do the thinking, the AI does the modelling, or both
  
        </motion.p>

        <motion.p
          animate={{ opacity: 1 }}
          className="mb-10 max-w-md text-sm text-muted-foreground/60"
          initial={{ opacity: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          Import Excel, write rows as functions, run the solver, diff the output —
          all from the CLI or through the agent loop.
        </motion.p>

        {/* clerk waitlist */}
        <motion.div
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-sm"
          initial={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.4, delay: 0.25 }}
        >
          <Waitlist
            appearance={{
              elements: {
                rootBox: "bg-none border-none",
                card: "bg-transparent border-none",
                headerTitle: "text-2xl font-bold text-zinc-900 dark:text-zinc-100",
                headerSubtitle: "hidden",
                formButtonPrimary:
                  "",
                formFieldInput:
                  "rounded-lg border-zinc-300 dark:border-zinc-700 focus:ring-indigo-500 focus:border-indigo-500",
                footerActionLink: "text-indigo-600 hover:text-indigo-500 font-semibold",
              },
            }}
          />
        </motion.div>
      </section>

      {/* screenshot placeholder */}
      <motion.section
        animate={{ opacity: 1, y: 0 }}
        className="relative z-10 mx-auto mb-20 max-w-5xl px-6"
        initial={{ opacity: 0, y: 16 }}
        transition={{ duration: 0.5, delay: 0.35 }}
      >
        <div className="relative overflow-hidden rounded-2xl border border-border bg-muted/40 shadow-2xl">
          {/* window chrome */}
          <div className="flex items-center gap-2 border-b border-border px-4 py-3">
            <div className="h-3 w-3 rounded-full bg-red-400/70" />
            <div className="h-3 w-3 rounded-full bg-yellow-400/70" />
            <div className="h-3 w-3 rounded-full bg-green-400/70" />
            <div className="ml-2 flex items-center gap-1.5 text-xs text-muted-foreground">
              <Terminal size={11} />
              expression agent
            </div>
          </div>
          {/* placeholder body */}
          <div className="flex aspect-[16/9] flex-col items-center justify-center gap-3 p-12 text-center">
            <div className="rounded-lg border border-dashed border-border/60 p-3 text-muted-foreground/40">
              <ChartLineUp size={28} />
            </div>
            <p className="text-sm text-muted-foreground/50">Screenshot coming soon</p>
          </div>
        </div>
      </motion.section>

      {/* features */}
      <section className="relative z-10 mx-auto max-w-5xl px-6 pb-24">
        <motion.h2
          animate={{ opacity: 1 }}
          className="mb-10 text-center text-sm font-medium uppercase tracking-widest text-muted-foreground/60"
          initial={{ opacity: 0 }}
          transition={{ duration: 0.4, delay: 0.4 }}
        >
          Everything you need, nothing you don&apos;t
        </motion.h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature, i) => {
            const Icon = feature.icon
            return (
              <motion.div
                key={feature.title}
                animate={{ opacity: 1, y: 0 }}
                className="group rounded-xl border border-border/60 bg-card p-5 transition-colors hover:border-border hover:bg-muted/40"
                initial={{ opacity: 0, y: 12 }}
                transition={{ duration: 0.35, delay: 0.45 + i * 0.05 }}
              >
                <div className="mb-3 inline-flex h-8 w-8 items-center justify-center rounded-lg bg-muted text-foreground/60 group-hover:text-foreground">
                  <Icon size={18} weight="duotone" />
                </div>
                <h3 className="mb-1.5 text-sm font-medium">{feature.title}</h3>
                <p className="text-xs leading-relaxed text-muted-foreground">
                  {feature.description}
                </p>
              </motion.div>
            )
          })}
        </div>
      </section>

      {/* footer */}
      <footer className="relative z-10 border-t border-border/40 px-8 py-6">
        <div className="mx-auto flex max-w-5xl items-center justify-between text-xs text-muted-foreground/50">
          <span>expression — spreadsheets as code</span>
          <span>built with Claude</span>
        </div>
      </footer>
    </div>
  )
}
