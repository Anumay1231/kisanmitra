import { useEffect, useState, type FormEvent } from 'react'
import { ArrowRight, CaretDown } from '@phosphor-icons/react'
import { inr, type Machine } from '../api'

/**
 * Quick purchase-plan form. It does not calculate anything itself: it turns the choices into a
 * question, so the agent looks up the price and runs the EMI calculator tool.
 */
export function PlanCard({ machines, onAsk, disabled }: {
  machines: Machine[]
  onAsk: (question: string) => void
  disabled: boolean
}) {
  const tractors = machines.filter((m) => m.category === 'tractor' && m.stock > 0)
  const [model, setModel] = useState('')
  const [subsidy, setSubsidy] = useState('40')
  const [down, setDown] = useState('100000')
  const [years, setYears] = useState('5')

  useEffect(() => {
    if (!model && tractors.length) setModel(tractors[0].model)
  }, [model, tractors])

  const price = tractors.find((m) => m.model === model)?.price_inr

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!model) return
    onAsk(
      `Plan a purchase of the ${model} with ${Number(subsidy) || 0}% subsidy and Rs ${inr(Number(down) || 0)} ` +
        `down payment over ${Number(years) || 5} years. What is the EMI?`,
    )
  }

  const field = 'mt-1.5 w-full rounded-xl border border-ink/80 bg-card px-3.5 py-2.5 text-base text-ink tabular-nums'

  return (
    <form onSubmit={submit} className="rounded-[var(--radius-card)] bg-card p-6" aria-labelledby="plan-h">
      <h2 id="plan-h" className="font-display text-xl font-extrabold tracking-tight text-ink">
        Plan a purchase
      </h2>
      <p className="mt-1 text-sm text-mute">KisanMitra checks the price and works out the EMI with its calculator.</p>

      <div className="mt-5 space-y-4">
        <div>
          <label htmlFor="plan-model" className="text-sm font-semibold text-ink">
            Tractor
          </label>
          <div className="relative">
          <select
            id="plan-model"
            name="model"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className={`${field} appearance-none pr-10`}
          >
            {tractors.map((m) => (
              <option key={m.model} value={m.model}>
                {m.model}, {m.hp} hp
              </option>
            ))}
          </select>
          <CaretDown
            size={16}
            weight="bold"
            className="pointer-events-none absolute top-1/2 right-3.5 mt-[3px] -translate-y-1/2 text-ink"
            aria-hidden
          />
          </div>
          {price != null && <p className="mt-1 text-xs text-mute">Listed at Rs {inr(price)}</p>}
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label htmlFor="plan-subsidy" className="text-sm font-semibold text-ink">
              Subsidy %
            </label>
            <input
              id="plan-subsidy"
              name="subsidy"
              inputMode="decimal"
              autoComplete="off"
              value={subsidy}
              onChange={(e) => setSubsidy(e.target.value.replace(/[^\d.]/g, ''))}
              className={field}
            />
          </div>
          <div>
            <label htmlFor="plan-down" className="text-sm font-semibold text-ink">
              Down (Rs)
            </label>
            <input
              id="plan-down"
              name="down_payment"
              inputMode="numeric"
              autoComplete="off"
              value={down}
              onChange={(e) => setDown(e.target.value.replace(/\D/g, ''))}
              className={field}
            />
          </div>
          <div>
            <label htmlFor="plan-years" className="text-sm font-semibold text-ink">
              Years
            </label>
            <input
              id="plan-years"
              name="years"
              inputMode="numeric"
              autoComplete="off"
              value={years}
              onChange={(e) => setYears(e.target.value.replace(/\D/g, '').slice(0, 2))}
              className={field}
            />
          </div>
        </div>
      </div>

      <button
        type="submit"
        disabled={disabled || !model}
        className="mt-6 flex w-full items-center justify-center gap-2 rounded-[var(--radius-card)] bg-lime px-6 py-3 text-base font-semibold text-on-lime hover:bg-lime-hover active:scale-[0.98] disabled:opacity-50"
      >
        Work out the EMI
        <ArrowRight size={18} weight="bold" aria-hidden />
      </button>
    </form>
  )
}
