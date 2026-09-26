import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { AnimatePresence, MotionConfig, motion } from 'motion/react'
import { ArrowUp, Moon, Plus, SlidersHorizontal, Square, Sun, Tractor, Warning, X } from '@phosphor-icons/react'
import { getHealth, getInventory, streamChat, type AdviceCard, type Health, type Machine, type StreamEvent } from './api'
import { AnswerText, CardFooter } from './components/Answer'
import { Sidebar } from './components/Sidebar'
import { Trace, type Step } from './components/Trace'
import { SUGGESTIONS, toolMeta } from './tools'

interface Turn {
  id: string
  question: string
  steps: Step[]
  thinking: boolean
  status: 'running' | 'done' | 'error' | 'stopped'
  answer?: string
  card?: AdviceCard
  latencyMs?: number
  error?: string
}

const newId = () => (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2))

function applyEvent(turn: Turn, e: StreamEvent): Turn {
  switch (e.type) {
    case 'thinking':
      return { ...turn, thinking: true }
    case 'tool_start':
      return { ...turn, thinking: false, steps: [...turn.steps, { id: e.id, tool: e.tool, input: e.input, done: false }] }
    case 'tool_end':
      return {
        ...turn,
        steps: turn.steps.map((s) => (s.id === e.id ? { ...s, output: e.output, error: e.error, done: true } : s)),
      }
    case 'final':
      return { ...turn, thinking: false, status: 'done', answer: e.answer, card: e.card, latencyMs: e.latency_ms }
    case 'error':
      return { ...turn, thinking: false, status: 'error', error: e.message }
  }
}

function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() =>
    document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light',
  )
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('km-theme', theme)
    } catch {
      /* private mode: theme just won't be remembered */
    }
  }, [theme])
  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))] as const
}

export default function App() {
  const [theme, toggleTheme] = useTheme()
  const [health, setHealth] = useState<Health | null>(null)
  const [offline, setOffline] = useState(false)
  const [machines, setMachines] = useState<Machine[]>([])
  const [turns, setTurns] = useState<Turn[]>([])
  const [draft, setDraft] = useState('')
  const [sessionId, setSessionId] = useState(newId)
  const [drawer, setDrawer] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const drawerTrigger = useRef<HTMLButtonElement>(null)
  const busy = turns.some((t) => t.status === 'running')

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setOffline(true))
    getInventory().then((d) => setMachines(d.machines)).catch(() => {})
  }, [])

  // Keep the newest content in view while the agent streams, unless the user scrolled up.
  useEffect(() => {
    const el = scrollRef.current
    if (!el || !turns.length) return
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 240) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [turns])

  useEffect(() => {
    if (!drawer) return
    const trigger = drawerTrigger.current
    const onKey = (e: globalThis.KeyboardEvent) => e.key === 'Escape' && setDrawer(false)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      trigger?.focus() // give focus back to the button that opened the drawer
    }
  }, [drawer])

  const ask = useCallback(
    async (question: string) => {
      const q = question.trim()
      if (!q || busy) return
      const id = newId()
      setTurns((ts) => [...ts, { id, question: q, steps: [], thinking: true, status: 'running' }])
      setDraft('')
      const ctrl = new AbortController()
      abortRef.current = ctrl
      const update = (e: StreamEvent) => setTurns((ts) => ts.map((t) => (t.id === id ? applyEvent(t, e) : t)))
      try {
        await streamChat(q, sessionId, update, ctrl.signal)
        setTurns((ts) =>
          ts.map((t) =>
            t.id === id && t.status === 'running' ? { ...t, status: 'error', error: 'The answer ended early.' } : t,
          ),
        )
      } catch (err) {
        const stopped = ctrl.signal.aborted
        setTurns((ts) =>
          ts.map((t) =>
            t.id === id
              ? {
                  ...t,
                  thinking: false,
                  status: stopped ? 'stopped' : 'error',
                  error: stopped ? undefined : `Could not reach the server (${(err as Error).message}).`,
                }
              : t,
          ),
        )
      } finally {
        abortRef.current = null
        inputRef.current?.focus()
      }
    },
    [busy, sessionId],
  )

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    ask(draft)
  }
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      ask(draft)
    }
  }
  const newChat = () => {
    abortRef.current?.abort()
    setTurns([])
    setSessionId(newId())
    inputRef.current?.focus()
  }

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex h-full flex-col">
        <a
          href="#composer"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2"
        >
          Skip to question box
        </a>

        {/* Header */}
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-line bg-surface px-4 sm:px-6">
          <span className="flex size-9 items-center justify-center rounded-xl bg-accent text-accent-ink">
            <Tractor size={20} weight="fill" aria-hidden />
          </span>
          <div className="min-w-0">
            <h1 translate="no" className="text-[15px] leading-tight font-semibold tracking-tight">
              KisanMitra
            </h1>
            <p className="truncate text-xs text-ink-3">Dealership assistant</p>
          </div>

          {health && (
            <span
              className={`ml-2 hidden rounded-full px-2.5 py-1 text-xs font-medium md:inline-block ${
                health.mode === 'demo' ? 'bg-warn-soft text-warn' : 'bg-accent-soft text-accent'
              }`}
              title={
                health.mode === 'demo'
                  ? 'No GROQ_API_KEY set: a rule-based router calls the real tools instead of the LLM'
                  : 'LangChain tool-calling agent on Groq'
              }
            >
              {health.mode === 'demo' ? 'Demo mode, no LLM' : `Agent: ${health.model ?? 'Groq'}`}
            </span>
          )}

          <div className="ml-auto flex items-center gap-1">
            <button
              type="button"
              onClick={newChat}
              disabled={!turns.length}
              className="flex h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-medium text-ink-2 hover:bg-surface-2 disabled:opacity-40 disabled:hover:bg-transparent"
            >
              <Plus size={16} aria-hidden />
              <span className="hidden sm:inline">New chat</span>
              <span className="sr-only sm:hidden">New chat</span>
            </button>
            <button
              type="button"
              onClick={toggleTheme}
              aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              className="flex size-9 items-center justify-center rounded-lg text-ink-2 hover:bg-surface-2"
            >
              {theme === 'dark' ? <Sun size={18} aria-hidden /> : <Moon size={18} aria-hidden />}
            </button>
            <button
              ref={drawerTrigger}
              type="button"
              onClick={() => setDrawer(true)}
              aria-label="Show tools and stock"
              className="flex size-9 items-center justify-center rounded-lg text-ink-2 hover:bg-surface-2 lg:hidden"
            >
              <SlidersHorizontal size={18} aria-hidden />
            </button>
          </div>
        </header>

        {offline && (
          <div role="alert" className="flex items-center gap-2 bg-warn-soft px-4 py-2 text-sm text-warn sm:px-6">
            <Warning size={16} weight="fill" aria-hidden />
            Can't reach the KisanMitra server. Start it with <code className="font-mono">python server.py</code> and
            reload.
          </div>
        )}

        <div className="flex min-h-0 flex-1">
          {/* Conversation */}
          <main className="flex min-w-0 flex-1 flex-col">
            <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
              <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
                {turns.length === 0 ? (
                  <EmptyState onPick={ask} disabled={busy || offline} />
                ) : (
                  <ol className="space-y-10" aria-label="Conversation">
                    {turns.map((t) => (
                      <TurnView key={t.id} turn={t} />
                    ))}
                  </ol>
                )}
              </div>
            </div>

            {/* Composer */}
            <div className="shrink-0 border-t border-line bg-bg">
              <form
                onSubmit={onSubmit}
                className="mx-auto w-full max-w-3xl px-4 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-6"
              >
                <label htmlFor="composer" className="sr-only">
                  Ask KisanMitra
                </label>
                <div className="flex items-end gap-2 rounded-2xl border border-line bg-surface p-2 shadow-[0_1px_2px_rgb(20_26_23/0.05)] focus-within:border-accent">
                  <textarea
                    id="composer"
                    name="message"
                    ref={inputRef}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={onKeyDown}
                    rows={1}
                    maxLength={2000}
                    autoComplete="off"
                    placeholder="Ask about stock, EMI, service, parts or weather…"
                    className="field-sizing-content max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-[15px] text-ink placeholder:text-ink-3 focus:outline-none"
                  />
                  {busy ? (
                    <button
                      type="button"
                      onClick={() => abortRef.current?.abort()}
                      aria-label="Stop"
                      className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-surface-2 text-ink hover:bg-line active:scale-[0.97]"
                    >
                      <Square size={14} weight="fill" aria-hidden />
                    </button>
                  ) : (
                    <button
                      type="submit"
                      disabled={!draft.trim() || offline}
                      aria-label="Send"
                      className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-ink hover:opacity-90 active:scale-[0.97] disabled:opacity-35"
                    >
                      <ArrowUp size={18} weight="bold" aria-hidden />
                    </button>
                  )}
                </div>
                <p className="mt-2 hidden text-center text-xs text-ink-3 sm:block">
                  Enter to send, Shift+Enter for a new line. Dealership data is synthetic.
                </p>
              </form>
            </div>
          </main>

          {/* Sidebar (desktop) */}
          <aside className="hidden w-80 shrink-0 overflow-y-auto border-l border-line bg-bg px-5 py-8 lg:block">
            <Sidebar health={health} machines={machines} />
          </aside>
        </div>

        {/* Sidebar (mobile drawer) */}
        <AnimatePresence>
          {drawer && (
            <motion.div className="fixed inset-0 z-40 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <button
                type="button"
                aria-label="Close"
                tabIndex={-1}
                className="absolute inset-0 bg-black/40"
                onClick={() => setDrawer(false)}
              />
              <motion.div
                role="dialog"
                aria-modal="true"
                aria-label="Tools and stock"
                initial={{ x: '100%' }}
                animate={{ x: 0 }}
                exit={{ x: '100%' }}
                transition={{ type: 'spring', stiffness: 380, damping: 38 }}
                className="absolute inset-y-0 right-0 w-[min(22rem,90vw)] overflow-y-auto overscroll-contain bg-bg px-5 py-5 shadow-xl"
              >
                <div className="mb-4 flex justify-end">
                  <button
                    type="button"
                    autoFocus
                    onClick={() => setDrawer(false)}
                    aria-label="Close"
                    className="flex size-9 items-center justify-center rounded-lg text-ink-2 hover:bg-surface-2"
                  >
                    <X size={18} aria-hidden />
                  </button>
                </div>
                <Sidebar health={health} machines={machines} />
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </MotionConfig>
  )
}

function EmptyState({ onPick, disabled }: { onPick: (q: string) => void; disabled: boolean }) {
  return (
    <div className="pt-4 sm:pt-10">
      <h2 className="text-3xl font-semibold tracking-tight text-balance text-ink sm:text-4xl">
        What does the customer need today?
      </h2>
      <p className="mt-3 max-w-[56ch] text-[15px] leading-relaxed text-ink-2">
        KisanMitra checks the dealership's stock, service records, spare parts, weather and subsidy rules, then does
        the EMI and fuel maths with a calculator.
      </p>
      <h3 className="mt-10 text-sm font-medium text-ink-3">Try a question</h3>
      <ul className="mt-3 grid grid-cols-1 overflow-hidden rounded-2xl border border-line bg-surface sm:grid-cols-2">
        {SUGGESTIONS.map((s, i) => {
          const meta = toolMeta(s.tool)
          const Icon = meta.icon
          return (
            <li
              key={s.text}
              className={`border-line ${i > 0 ? 'border-t' : ''} ${i === 1 ? 'sm:border-t-0' : ''} ${
                i % 2 === 1 ? 'sm:border-l' : ''
              }`}
            >
              <button
                type="button"
                disabled={disabled}
                onClick={() => onPick(s.text)}
                className="flex h-full w-full items-start gap-3 px-4 py-3.5 text-left hover:bg-surface-2 disabled:opacity-50 disabled:hover:bg-transparent"
              >
                <Icon size={18} className="mt-0.5 shrink-0 text-accent" aria-hidden />
                <span>
                  <span className="block text-xs text-ink-3">{meta.label}</span>
                  <span className="mt-0.5 block text-sm leading-snug text-ink">{s.text}</span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function TurnView({ turn }: { turn: Turn }) {
  return (
    <motion.li
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-4"
    >
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-md bg-accent-soft px-4 py-2.5 text-[15px] leading-relaxed text-ink">
          {turn.question}
        </p>
      </div>

      <Trace steps={turn.steps} running={turn.status === 'running'} thinking={turn.thinking} latencyMs={turn.latencyMs} />

      {turn.status === 'running' && !turn.answer && (
        <div className="space-y-2" aria-hidden>
          <div className="h-4 w-11/12 animate-pulse rounded bg-surface-2" />
          <div className="h-4 w-4/6 animate-pulse rounded bg-surface-2" />
        </div>
      )}

      {turn.answer && <AnswerText text={turn.answer} />}
      {turn.card && <CardFooter card={turn.card} />}

      {turn.status === 'error' && (
        <div role="alert" className="flex gap-2.5 rounded-xl bg-warn-soft px-3.5 py-2.5 text-sm text-warn">
          <Warning size={16} weight="fill" className="mt-0.5 shrink-0" aria-hidden />
          <span>{turn.error ?? 'Something went wrong.'} Try asking again.</span>
        </div>
      )}
      {turn.status === 'stopped' && <p className="text-sm text-ink-3">Stopped.</p>}
    </motion.li>
  )
}
