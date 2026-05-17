import { create } from "zustand"

const DEFAULT_THINKING_WORDS = [
  "expressing",
  "vlookuping",
  "xlookuping",
  "pivottabling",
  "sumiffing",
  "indexmatching",
  "iferroring",
  "concatenating",
  "annualizing",
  "amortizing",
  "discountcashflowing",
  "backenveloping",
  "numbrcrunching",
  "irring",
  "xirring",
  "npving",
  "goalseeking",
  "whatiffing",
  "montecarloing",
  "bootstrapping",
  "regressing",
  "extrapolating",
  "interpolating",
  "logarithming",
  "exponentiating",
  "factorialing",
  "sigmasumming",
  "integrating",
  "differentiating",
  "ctrlshiftentering",
  "freezepaning",
]

type LogoStore = {
  isThinking: boolean
  thinkingWords: string[]
  cycleId: number
  startThinking: (words?: string[]) => void
  stopThinking: () => void
}

export const useLogoStore = create<LogoStore>()((set) => ({
  isThinking: false,
  thinkingWords: DEFAULT_THINKING_WORDS,
  cycleId: 0,
  startThinking: (words = DEFAULT_THINKING_WORDS) =>
    set((state) => ({
      isThinking: true,
      thinkingWords: words.length > 0 ? words : DEFAULT_THINKING_WORDS,
      // Only start a new cycle (remount) when transitioning from idle → thinking.
      // Repeated calls while already thinking (e.g. submitted → streaming) must
      // not bump cycleId or the animation resets mid-stream.
      cycleId: state.isThinking ? state.cycleId : state.cycleId + 1,
    })),
  stopThinking: () =>
    set({
      isThinking: false,
      thinkingWords: DEFAULT_THINKING_WORDS,
    }),
}))

export { DEFAULT_THINKING_WORDS }
