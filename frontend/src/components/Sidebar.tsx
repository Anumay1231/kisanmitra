import type { Health, Machine } from '../api'
import { inr } from '../api'
import { toolMeta } from '../tools'

const STATUS: Record<string, { text: string; cls: string }> = {
  ok: { text: 'Ready', cls: 'bg-pos-bg text-pos' },
  needs_key: { text: 'Needs key', cls: 'bg-warn-bg text-warn' },
  unavailable: { text: 'Off', cls: 'bg-card-2 text-mute' },
}

export function Sidebar({ health, machines }: { health: Health | null; machines: Machine[] }) {
  return (
    <div className="space-y-4">
      <section aria-labelledby="tools-h" className="rounded-[var(--radius-card)] bg-card p-5">
        <h2 id="tools-h" className="font-display text-lg font-extrabold tracking-tight text-ink">
          What it can check
        </h2>
        <p className="mt-1 text-sm text-mute">The AI picks the right tools. It never makes up a figure.</p>
        <ul className="mt-4 space-y-1">
          {(health?.tools ?? []).map((t) => {
            const meta = toolMeta(t.name)
            const Icon = meta.icon
            const st = STATUS[t.status] ?? STATUS.ok
            return (
              <li key={t.name} className="flex items-center gap-3 py-1.5">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-card-2 text-ink">
                  <Icon size={17} aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold text-ink">{meta.label}</div>
                  <div className="truncate text-xs text-mute">{meta.source}</div>
                </div>
                <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${st.cls}`}>{st.text}</span>
              </li>
            )
          })}
          {!health &&
            Array.from({ length: 5 }).map((_, i) => (
              <li key={i} className="flex items-center gap-3 py-1.5">
                <span className="size-9 animate-pulse rounded-full bg-card-2" />
                <span className="h-4 w-2/3 animate-pulse rounded bg-card-2" />
              </li>
            ))}
        </ul>
      </section>

      <section aria-labelledby="stock-h" className="rounded-[var(--radius-card)] bg-card p-5">
        <h2 id="stock-h" className="font-display text-lg font-extrabold tracking-tight text-ink">
          In the yard
        </h2>
        <p className="mt-1 text-sm text-mute">Machines in the dealership database (sample data).</p>
        <table className="mt-3 w-full text-sm">
          <thead className="sr-only">
            <tr>
              <th>Model</th>
              <th>Price</th>
              <th>Stock</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {machines.map((m) => (
              <tr key={m.model} className={m.stock === 0 ? 'text-mute' : 'text-ink'}>
                <td className="py-2 pr-2">
                  <div className="truncate font-semibold">{m.model}</div>
                  <div className="text-xs text-mute">
                    {m.category[0].toUpperCase() + m.category.slice(1)}
                    {m.hp ? `, ${m.hp} hp` : ''}
                  </div>
                </td>
                <td className="py-2 pr-2 text-right text-xs tabular-nums whitespace-nowrap">Rs {inr(m.price_inr)}</td>
                <td className="py-2 text-right text-xs whitespace-nowrap">
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
