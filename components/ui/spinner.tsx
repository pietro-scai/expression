import { cn } from "@/lib/utils"
import { HugeiconsIcon } from "@hugeicons/react"
import { Loading03Icon } from "@hugeicons/core-free-icons"
import type React from "react"

function Spinner({ className, ...props }: React.ComponentProps<"svg">) {
  return (
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    <HugeiconsIcon icon={Loading03Icon} strokeWidth={2} role="status" aria-label="Loading" className={cn("size-4 animate-spin", className)} {...(props as any)} />
  )
}

export { Spinner }
