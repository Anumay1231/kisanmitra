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
    <div className="space-y-3 text-[15px] leading-relaxed text-ink-2">
      {blocks
        .filter((b) => b.lines.length)
        .map((b, i) =>
          b.list ? (
            <ul key={i} className="space-y-1.5 pl-1">
              {b.lines.map((l, j) => (
                <li key={j} className="flex gap-2.5">
                  <span className="mt-[9px] h-px w-2.5 shrink-0 bg-ink-3" aria-hidden />
                  <span>
                    <Inline text={l} />
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p key={i} className="max-w-[68ch]">
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

const CONFIDENCE: Record<AdviceCard['confidence'], { label: string; bars: number }> = {
  high: { label: 'High confidence: every figure came from a tool', bars: 3 },
  medium: { label: 'Medium confidence', bars: 2 },
  low: { label: 'Low confidence: some data was missing', bars: 1 },
}

/** The structured AdviceCard (PydanticOutputParser) shown under the answer. */
export function CardFooter({ card }: { card: AdviceCard }) {
  const conf = CONFIDENCE[card.confidence] ?? CONFIDENCE.medium
  return (
    <div className="space-y-3">
      {card.key_figures.length > 0 && (
        <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {card.key_figures.map((f) => {
            // "EMI Rs 5,586/month" -> label "EMI", value "Rs 5,586/month"
            const m = f.match(/^(.*?)\s*[:=]?\s*((?:Rs|₹)\s?[\d,.]+.*|[\d,.]+\s*(?:mm|litres|L|hp|%|jobs?).*)$/i)
            const label = m?.[1]?.trim() || 'Figure'
            const value = m?.[2] ?? f
            return (
              <div key={f} className="rounded-xl border border-line bg-surface px-3.5 py-2.5">
                <dt className="text-xs text-ink-3">{label}</dt>
                <dd className="mt-0.5 text-base font-semibold tabular-nums tracking-tight text-ink">{value}</dd>
              </div>
            )
          })}
        </dl>
      )}

      {card.data_gaps && (
        <div className="flex gap-2.5 rounded-xl bg-warn-soft px-3.5 py-2.5 text-sm text-warn" role="note">
          <Warning size={16} weight="fill" className="mt-0.5 shrink-0" aria-hidden />
          <span>{card.data_gaps}</span>
        </div>
      )}

      <div className="flex items-center gap-2 text-xs text-ink-3">
        <span className="flex items-end gap-0.5" aria-hidden>
          {[1, 2, 3].map((b) => (
            <span
              key={b}
              className={`w-1 rounded-sm ${b <= conf.bars ? 'bg-accent' : 'bg-line'}`}
              style={{ height: 4 + b * 3 }}
            />
          ))}
        </span>
        <span>{conf.label}</span>
      </div>
    </div>
  )
}
