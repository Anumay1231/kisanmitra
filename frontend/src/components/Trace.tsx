import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { CaretDown, CheckCircle, CircleNotch, Warning } from '@phosphor-icons/react'
import { toolMeta } from '../tools'

export interface Step {
  id: string
  tool: string
  input: unknown
  output?: string
  error?: boolean
  done: boolean
}

function Args({ input }: { input: unknown }) {
  if (input == null) return null
  if (typeof input !== 'object') return <code className="font-mono text-xs text-ink-2">{String(input)}</code>
  const entries = Object.entries(input as Record<string, unknown>).filter(([, v]) => v !== null && v !== undefined)
  if (!entries.length) return <span className="text-xs text-ink-3">no arguments</span>
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Arguments">
      {entries.map(([k, v]) => (
        <li key={k} className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-ink-2">
          {k}=<span className="text-ink">{String(v)}</span>
        </li>
      ))}
    </ul>
  )
}

function Output({ text, error }: { text: string; error?: boolean }) {
  const [full, setFull] = useState(false)
  const long = text.length > 280
  const shown = full || !long ? text : text.slice(0, 280) + '…'
  // Tools return "a=1; b=2" rows; put each field on its own line so it reads like a record.
  const pretty = shown.replace(/; (?=[a-z_()%0-9]+=)/g, '\n  ')
  return (
    <div>
      <pre
        className={`mt-2 max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-lg px-3 py-2 font-mono text-[11.5px] leading-relaxed ${
          error ? 'bg-warn-soft text-warn' : 'bg-surface-2 text-ink-2'
        }`}
      >
        {pretty}
      </pre>
      {long && (
        <button
          type="button"
          onClick={() => setFull((f) => !f)}
          className="mt-1 text-xs font-medium text-accent hover:underline"
        >
          {full ? 'Show less' : 'Show full output'}
        </button>
      )}
    </div>
  )
}

interface TraceProps {
  steps: Step[]
  running: boolean
  thinking: boolean
  latencyMs?: number
}

/** The agent's tool calls in order: what it called, with which arguments, and what came back. */
export function Trace({ steps, running, thinking, latencyMs }: TraceProps) {
  const [open, setOpen] = useState<boolean | null>(null)
  const expanded = open ?? running
  const failures = steps.filter((s) => s.error).length

  if (!steps.length && !running) return null

  const summary = running
    ? steps.length
      ? `Calling ${toolMeta(steps[steps.length - 1].tool).label.toLowerCase()}…`
      : 'Deciding which tools to use…'
    : `Checked ${steps.length} ${steps.length === 1 ? 'source' : 'sources'}` +
      (latencyMs != null ? ` in ${(latencyMs / 1000).toFixed(1)} s` : '')

  return (
    <div className="rounded-xl border border-line bg-surface">
      <button
        type="button"
        onClick={() => setOpen(!expanded)}
        aria-expanded={expanded}
        className="flex w-full items-center gap-3 rounded-xl px-3.5 py-2.5 text-left"
      >
        {running ? (
          <CircleNotch size={16} className="shrink-0 animate-spin text-accent" aria-hidden />
        ) : failures ? (
          <Warning size={16} weight="fill" className="shrink-0 text-warn" aria-hidden />
        ) : (
          <CheckCircle size={16} weight="fill" className="shrink-0 text-accent" aria-hidden />
        )}
        <span className="text-sm font-medium text-ink" aria-live="polite">
          {summary}
        </span>
        {!running && failures > 0 && (
          <span className="text-xs text-warn">
            {failures} failed
          </span>
        )}
        <span className="ml-auto hidden items-center gap-1 sm:flex" aria-hidden>
          {steps.map((s) => {
            const Icon = toolMeta(s.tool).icon
            return <Icon key={s.id} size={15} className={s.error ? 'text-warn' : 'text-ink-3'} />
          })}
        </span>
        <CaretDown
          size={14}
          className={`shrink-0 text-ink-3 transition-transform ${expanded ? 'rotate-180' : ''}`}
          aria-hidden
        />
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <ol className="border-t border-line px-3.5 py-3">
              {steps.map((s, i) => {
                const meta = toolMeta(s.tool)
                const Icon = meta.icon
                return (
                  <li key={s.id} className="relative flex gap-3 pb-4 last:pb-0">
                    {i < steps.length - 1 && (
                      <span className="absolute top-8 bottom-0 left-[13px] w-px bg-line" aria-hidden />
                    )}
                    <span
                      className={`flex size-7 shrink-0 items-center justify-center rounded-lg ${
                        s.error ? 'bg-warn-soft text-warn' : 'bg-accent-soft text-accent'
                      }`}
                    >
                      <Icon size={15} weight="bold" aria-hidden />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-baseline gap-x-2">
                        <span className="text-sm font-medium text-ink">{meta.label}</span>
                        <span className="text-xs text-ink-3">{meta.source}</span>
                        <code className="font-mono text-[11px] text-ink-3">{s.tool}</code>
                      </div>
                      <div className="mt-1.5">
                        <Args input={s.input} />
                      </div>
                      {s.done ? (
                        <Output text={s.output ?? ''} error={s.error} />
                      ) : (
                        <div className="mt-2 h-8 animate-pulse rounded-lg bg-surface-2" aria-label="Waiting for result" />
                      )}
                    </div>
                  </li>
                )
              })}
              {running && thinking && steps.every((s) => s.done) && (
                <li className="flex items-center gap-3 text-sm text-ink-3">
                  <span className="flex size-7 items-center justify-center">
                    <CircleNotch size={15} className="animate-spin" aria-hidden />
                  </span>
                  Reading the results…
                </li>
              )}
            </ol>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
