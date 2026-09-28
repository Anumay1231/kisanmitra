import { Warning } from '@phosphor-icons/react'
import type { AdviceCard } from '../api'

/** Minimal formatting for agent text: paragraphs, "- " bullet lists and **bold**. */
function Inline({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith('**') && p.endsWith('**') ? (
          <strong key={i} className="font-semibold text-ink">
            {p.slice(2, -2)}
          </strong>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  )
}

export function AnswerText({ text }: { text: string }) {
  const blocks: { list: boolean; lines: string[] }[] = []
  for (const raw of text.split('\n')) {
    const line = raw.trimEnd()
    const bullet = /^\s*([-*•]|\d+\.)\s+/.test(line)
    if (!line.trim()) {
      blocks.push({ list: false, lines: [] })
      continue
    }
    const last = blocks[blocks.length - 1]
    const content = bullet ? line.replace(/^\s*([-*•]|\d+\.)\s+/, '') : line
    if (last && last.list === bullet && last.lines.length) last.lines.push(content)
    else blocks.push({ list: bullet, lines: [content] })
  }
  return (
    <div className="space-y-3 text-base leading-relaxed text-body">
      {blocks
        .filter((b) => b.lines.length)
        .map((b, i) =>
          b.list ? (
            <ul key={i} className="divide-y divide-line overflow-hidden rounded-2xl bg-card-2">
              {b.lines.map((l, j) => (
                <li key={j} className="px-4 py-2.5 text-[15px]">
                  <Inline text={l} />
                </li>
              ))}
            </ul>
          ) : (
            <p key={i} className="max-w-[65ch]">
              {b.lines.map((l, j) => (
                <span key={j}>
                  {j > 0 && <br />}
                  <Inline text={l} />
                </span>
              ))}
            </p>
          ),
        )}
    </div>
  )
}

const CONFIDENCE: Record<AdviceCard['confidence'], { label: string; cls: string }> = {
  high: { label: 'High confidence: every figure came from a tool', cls: 'bg-pos-bg text-pos' },
  medium: { label: 'Medium confidence', cls: 'bg-warn-bg text-warn' },
  low: { label: 'Low confidence: some data was missing', cls: 'bg-neg-bg text-neg' },
}

function splitFigure(f: string) {
  // "EMI Rs 5,586/month" -> label "EMI", value "Rs 5,586/month"
  const m = f.match(/^(.*?)\s*[:=]?\s*((?:Rs|₹)\s?[\d,.]+.*|[\d,.]+\s*(?:mm|litres|L|hp|%|jobs?|matching).*)$/i)
  return { label: m?.[1]?.trim() || 'Result', value: m?.[2] ?? f }
}

/** The structured AdviceCard (PydanticOutputParser) shown under the answer. */
export function CardFooter({ card }: { card: AdviceCard }) {
  const conf = CONFIDENCE[card.confidence] ?? CONFIDENCE.medium
  // Put the monthly EMI first when there is one: it is the number a buyer cares about most.
  const figures = card.key_figures
    .map(splitFigure)
    .sort((a, b) => Number(/emi/i.test(b.label)) - Number(/emi/i.test(a.label)))
  return (
    <div className="space-y-4">
      {figures.length > 0 && (
        <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {figures.map((f, i) => (
            <div
              key={f.label + f.value}
              className={`rounded-2xl px-4 py-3 ${
                // The first figure is the headline number (usually the EMI or price); it gets the full row.
                i === 0 && figures.length !== 2 ? 'bg-pos-bg sm:col-span-2' : 'bg-card-2'
              }`}
            >
              <dt className="text-xs font-medium text-mute">{f.label}</dt>
              <dd
                className={`mt-0.5 font-display font-extrabold tracking-tight text-ink tabular-nums ${
                  i === 0 && figures.length !== 2 ? 'text-3xl' : 'text-xl'
                }`}
              >
                {f.value}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {card.data_gaps && (
        <div className="flex gap-2.5 rounded-2xl bg-warn-bg px-4 py-3 text-sm text-warn" role="note">
          <Warning size={16} weight="fill" className="mt-0.5 shrink-0" aria-hidden />
          <span>{card.data_gaps}</span>
        </div>
      )}

      <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${conf.cls}`}>{conf.label}</span>
    </div>
  )
}
