import type { Health, Machine } from '../api'
import { inr } from '../api'
import { toolMeta } from '../tools'

const STATUS: Record<string, { text: string; cls: string }> = {
  ok: { text: 'Ready', cls: 'text-accent' },
  needs_key: { text: 'Needs API key', cls: 'text-warn' },
  unavailable: { text: 'Not loaded', cls: 'text-ink-3' },
}

export function Sidebar({ health, machines }: { health: Health | null; machines: Machine[] }) {
  return (
    <div className="space-y-8">
      <section aria-labelledby="tools-h">
        <h2 id="tools-h" className="text-sm font-semibold text-ink">
          Tools the agent can call
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-ink-3">
          The model picks which of these to call for each question. It never makes up a price or figure.
        </p>
        <ul className="mt-3 divide-y divide-line rounded-xl border border-line bg-surface">
          {(health?.tools ?? []).map((t) => {
            const meta = toolMeta(t.name)
            const Icon = meta.icon
            const st = STATUS[t.status] ?? STATUS.ok
            return (
              <li key={t.name} className="flex items-center gap-3 px-3 py-2.5">
                <Icon size={17} className="shrink-0 text-ink-2" aria-hidden />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm text-ink">{meta.label}</div>
                  <div className="truncate text-xs text-ink-3">{meta.source}</div>
                </div>
                <span className={`shrink-0 text-xs font-medium ${st.cls}`}>{st.text}</span>
              </li>
            )
          })}
          {!health &&
            Array.from({ length: 5 }).map((_, i) => (
              <li key={i} className="px-3 py-3">
                <div className="h-4 w-2/3 animate-pulse rounded bg-surface-2" />
              </li>
            ))}
        </ul>
      </section>

      <section aria-labelledby="stock-h">
        <h2 id="stock-h" className="text-sm font-semibold text-ink">
          Machines at the dealership
        </h2>
        <p className="mt-1 text-xs text-ink-3">Synthetic data from the SQLite database.</p>
        <table className="mt-3 w-full text-sm">
          <thead className="sr-only">
            <tr>
              <th>Model</th>
              <th>Price</th>
              <th>Stock</th>
            </tr>
          </thead>
          <tbody>
            {machines.map((m) => (
              <tr key={m.model} className={m.stock === 0 ? 'text-ink-3' : 'text-ink'}>
                <td className="py-1.5 pr-2">
                  <div className="truncate">{m.model}</div>
                  <div className="text-xs text-ink-3">
                    {m.category}
                    {m.hp ? `, ${m.hp} hp` : ''}
                  </div>
                </td>
                <td className="py-1.5 pr-2 text-right text-xs tabular-nums whitespace-nowrap">
                  Rs {inr(m.price_inr)}
                </td>
                <td className="py-1.5 text-right text-xs whitespace-nowrap">
                  {m.stock === 0 ? 'Out of stock' : `${m.stock} left`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
