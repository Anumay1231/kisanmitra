import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { AnimatePresence, MotionConfig, motion } from 'motion/react'
import { ArrowUp, Moon, Plus, SlidersHorizontal, Square, Sun, Tractor, Warning, X } from '@phosphor-icons/react'
import { getHealth, getInventory, streamChat, type AdviceCard, type Health, type Machine, type StreamEvent } from './api'
import { AnswerText, CardFooter } from './components/Answer'
import { PlanCard } from './components/PlanCard'
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
      /* private mode: the theme just won't be remembered */
    }
  }, [theme])
  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))] as const
}

const iconBtn =
  'flex size-10 items-center justify-center rounded-full text-ink hover:bg-card-2 active:scale-[0.96] disabled:opacity-40'

export default function App() {
  const [theme, toggleTheme] = useTheme()
  const [health, setHealth] = useState<Health | null>(null)
  const [offline, setOffline] = useState(false)
  const [machines, setMachines] = useState<Machine[]>([])
  const [turns, setTurns] = useState<Turn[]>([])
  const [draft, setDraft] = useState('')
  const [sessionId, setSessionId] = useState(newId)
  const [drawer, setDrawer] = useState(false)
  const [cleared, setCleared] = useState<{ turns: Turn[]; sessionId: string } | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const drawerTrigger = useRef<HTMLButtonElement>(null)
  const busy = turns.some((t) => t.status === 'running')

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setOffline(true))
    getInventory()
      .then((d) => setMachines(d.machines))
      .catch(() => {})
  }, [])

  // Keep the newest content in view while the agent works, unless the user scrolled up to read.
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
      trigger?.focus() // return focus to the button that opened the drawer
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
  // Clearing the chat is undoable for a few seconds instead of asking for confirmation.
  const newChat = () => {
    abortRef.current?.abort()
    setCleared({ turns: turns.filter((t) => t.status !== 'running'), sessionId })
    setTurns([])
    setSessionId(newId())
    inputRef.current?.focus()
  }
  const undoClear = () => {
    if (!cleared) return
    setTurns(cleared.turns)
    setSessionId(cleared.sessionId)
    setCleared(null)
  }
  useEffect(() => {
    if (!cleared) return
    const t = setTimeout(() => setCleared(null), 8000)
    return () => clearTimeout(t)
  }, [cleared])
  useEffect(() => {
    if (turns.length) setCleared(null)
  }, [turns.length])

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex h-full flex-col">
        <a
          href="#composer"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-full focus:bg-card focus:px-4 focus:py-2"
        >
          Skip to question box
        </a>

        {/* Header */}
        <header className="flex h-16 shrink-0 items-center gap-3 bg-card px-4 sm:px-6">
          <span className="flex size-10 items-center justify-center rounded-full bg-lime text-on-lime">
            <Tractor size={22} weight="fill" aria-hidden />
          </span>
          <h1 translate="no" className="font-display text-xl font-extrabold tracking-tight">
            KisanMitra
          </h1>
          {health && (
            <span
              className={`ml-1 hidden rounded-full px-3 py-1 text-xs font-semibold md:inline-block ${
                health.mode === 'demo' ? 'bg-warn-bg text-warn' : 'bg-pos-bg text-pos'
              }`}
              title={
                health.mode === 'demo'
                  ? 'No working Groq key: a rule-based router calls the real tools instead of the AI model'
                  : 'LangChain tool-calling agent on Groq'
              }
            >
              {health.mode === 'demo' ? 'Demo mode, no LLM' : `AI agent: ${health.model ?? 'Groq'}`}
            </span>
          )}

          <div className="ml-auto flex items-center gap-1.5">
            <button
              type="button"
              onClick={newChat}
              disabled={!turns.length}
              className="flex h-10 items-center gap-1.5 rounded-full bg-canvas px-4 text-sm font-semibold text-ink hover:bg-line active:scale-[0.98] disabled:opacity-40 disabled:hover:bg-canvas"
            >
              <Plus size={16} weight="bold" aria-hidden />
              <span className="hidden sm:inline">New chat</span>
              <span className="sr-only sm:hidden">New chat</span>
            </button>
            <button
              type="button"
              onClick={toggleTheme}
              aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              className={iconBtn}
            >
              {theme === 'dark' ? <Sun size={20} aria-hidden /> : <Moon size={20} aria-hidden />}
            </button>
            <button
              ref={drawerTrigger}
              type="button"
              onClick={() => setDrawer(true)}
              aria-label="Show tools and stock"
              className={`${iconBtn} lg:hidden`}
            >
              <SlidersHorizontal size={20} aria-hidden />
            </button>
          </div>
        </header>

        {health?.warning && !offline && (
          <div role="status" className="flex items-start gap-2 bg-warn-bg px-4 py-2.5 text-sm text-warn sm:px-6">
            <Warning size={16} weight="fill" className="mt-0.5 shrink-0" aria-hidden />
            <span className="min-w-0 break-words">{health.warning}</span>
          </div>
        )}
        {offline && (
          <div role="alert" className="flex items-center gap-2 bg-warn-bg px-4 py-2.5 text-sm text-warn sm:px-6">
            <Warning size={16} weight="fill" aria-hidden />
            Can't reach the KisanMitra server. Start it by double-clicking <b>Start KisanMitra.bat</b>, then reload
            this page.
          </div>
        )}

        <div className="flex min-h-0 flex-1">
          <main className="flex min-w-0 flex-1 flex-col">
            <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
              {turns.length === 0 ? (
                <Home machines={machines} onAsk={ask} disabled={busy || offline} />
              ) : (
                <ol className="mx-auto w-full max-w-3xl space-y-8 px-4 py-8 sm:px-6" aria-label="Conversation">
                  {turns.map((t) => (
                    <TurnView key={t.id} turn={t} />
                  ))}
                </ol>
              )}
            </div>

            {/* Composer */}
            <div className="shrink-0">
              <form
                onSubmit={onSubmit}
                className="mx-auto w-full max-w-3xl px-4 pt-2 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-6"
              >
                <div aria-live="polite">
                  {cleared && (
                    <div className="mb-2 flex items-center justify-between gap-3 rounded-full bg-ink py-1.5 pr-1.5 pl-4 text-sm text-card">
                      <span>Chat cleared.</span>
                      <button
                        type="button"
                        onClick={undoClear}
                        className="rounded-full bg-lime px-4 py-1.5 text-sm font-semibold text-on-lime hover:bg-lime-hover"
                      >
                        Undo
                      </button>
                    </div>
                  )}
                </div>
                <label htmlFor="composer" className="sr-only">
                  Ask KisanMitra
                </label>
                <div className="flex items-end gap-2 rounded-[var(--radius-card)] border border-ink/80 bg-card p-2 pl-3 focus-within:border-ink focus-within:ring-2 focus-within:ring-lime">
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
                    className="field-sizing-content max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-2.5 text-base text-ink placeholder:text-mute focus:outline-none"
                  />
                  {busy ? (
                    <button
                      type="button"
                      onClick={() => abortRef.current?.abort()}
                      aria-label="Stop"
                      className="flex size-11 shrink-0 items-center justify-center rounded-full bg-ink text-card hover:opacity-85 active:scale-[0.96]"
                    >
                      <Square size={14} weight="fill" aria-hidden />
                    </button>
                  ) : (
                    <button
                      type="submit"
                      disabled={!draft.trim() || offline}
                      aria-label="Send"
                      className="flex size-11 shrink-0 items-center justify-center rounded-full bg-lime text-on-lime hover:bg-lime-hover active:scale-[0.96] disabled:opacity-40"
                    >
                      <ArrowUp size={20} weight="bold" aria-hidden />
                    </button>
                  )}
                </div>
                <p className="mt-2 hidden text-center text-xs text-mute sm:block">
                  Enter to send, Shift+Enter for a new line. Dealership data is sample data.
                </p>
              </form>
            </div>
          </main>

          <aside className="hidden w-[340px] shrink-0 overflow-y-auto py-6 pr-6 lg:block" aria-label="Tools and stock">
            <Sidebar health={health} machines={machines} />
          </aside>
        </div>

        {/* Mobile drawer */}
        <AnimatePresence>
          {drawer && (
            <motion.div
              className="fixed inset-0 z-40 lg:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <button
                type="button"
                aria-label="Close"
                tabIndex={-1}
                className="absolute inset-0 bg-ink/50"
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
                className="absolute inset-y-0 right-0 w-[min(24rem,92vw)] overflow-y-auto overscroll-contain bg-canvas p-4"
              >
                <div className="mb-3 flex justify-end">
                  <button
                    type="button"
                    autoFocus
                    onClick={() => setDrawer(false)}
                    aria-label="Close"
                    className={`${iconBtn} bg-card`}
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

function Home({ machines, onAsk, disabled }: { machines: Machine[]; onAsk: (q: string) => void; disabled: boolean }) {
  return (
    <div className="mx-auto grid w-full max-w-6xl gap-6 px-4 py-8 sm:px-6 sm:py-12 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] xl:gap-10">
      <div>
        <h2 className="font-display text-5xl leading-[0.95] font-extrabold tracking-tight text-balance text-ink sm:text-6xl">
          Ask the dealership anything.
        </h2>
        <p className="mt-4 max-w-[46ch] text-lg leading-relaxed text-body">
          Stock, EMI, service history, spare parts and spraying weather, answered from the dealership's own data.
        </p>

        <h3 className="mt-10 text-sm font-semibold text-ink">Try asking</h3>
        <ul className="mt-3 divide-y divide-line overflow-hidden rounded-[var(--radius-card)] bg-card">
          {SUGGESTIONS.map((s) => {
            const meta = toolMeta(s.tool)
            const Icon = meta.icon
            return (
              <li key={s.text}>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => onAsk(s.text)}
                  className="flex w-full items-center gap-3.5 px-5 py-3.5 text-left hover:bg-card-2 disabled:opacity-50 disabled:hover:bg-transparent"
                >
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-card-2 text-ink">
                    <Icon size={17} aria-hidden />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-xs font-medium text-mute">{meta.label}</span>
                    <span className="block text-[15px] leading-snug text-ink">{s.text}</span>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </div>

      <div className="xl:pt-2">
        <PlanCard machines={machines} onAsk={onAsk} disabled={disabled} />
      </div>
    </div>
  )
}

function TurnView({ turn }: { turn: Turn }) {
  return (
    <motion.li
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-3"
    >
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-[var(--radius-card)] rounded-br-lg bg-user px-5 py-3 text-base leading-relaxed text-on-user">
          {turn.question}
        </p>
      </div>

      <div className="space-y-4 rounded-[var(--radius-card)] bg-card p-4 sm:p-6">
        <Trace steps={turn.steps} running={turn.status === 'running'} thinking={turn.thinking} latencyMs={turn.latencyMs} />

        {turn.status === 'running' && !turn.answer && (
          <div className="space-y-2" aria-hidden>
            <div className="h-4 w-11/12 animate-pulse rounded-full bg-card-2" />
            <div className="h-4 w-4/6 animate-pulse rounded-full bg-card-2" />
          </div>
        )}

        {turn.answer && <AnswerText text={turn.answer} />}
        {turn.card && <CardFooter card={turn.card} />}

        {turn.status === 'error' && (
          <div role="alert" className="flex gap-2.5 rounded-2xl bg-neg-bg px-4 py-3 text-sm text-neg">
            <Warning size={16} weight="fill" className="mt-0.5 shrink-0" aria-hidden />
            <span>{turn.error ?? 'Something went wrong.'} Try asking again.</span>
          </div>
        )}
        {turn.status === 'stopped' && <p className="text-sm text-mute">Stopped.</p>}
      </div>
    </motion.li>
  )
}
