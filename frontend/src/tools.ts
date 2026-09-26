import {
  BookOpenText, Calculator, ChartLineUp, CloudSun, GasPump, Package, Question, Tractor, Wrench,
  type Icon,
} from '@phosphor-icons/react'

export interface ToolMeta { label: string; source: string; icon: Icon }

// Friendly names for the agent's tools. Keys match the @tool names in src/kisanmitra/tools.py.
export const TOOL_META: Record<string, ToolMeta> = {
  search_inventory: { label: 'Inventory', source: 'Dealership database', icon: Tractor },
  calculate_purchase_plan: { label: 'Purchase plan', source: 'EMI and subsidy calculator', icon: Calculator },
  search_service_records: { label: 'Service records', source: 'Dealership database', icon: Wrench },
  check_part_stock: { label: 'Spare parts', source: 'Dealership database', icon: Package },
  estimate_operating_cost: { label: 'Fuel cost', source: 'Diesel calculator', icon: GasPump },
  get_weather_forecast: { label: 'Weather', source: 'Open-Meteo API', icon: CloudSun },
  get_mandi_price: { label: 'Mandi prices', source: 'data.gov.in API', icon: ChartLineUp },
  lookup_scheme_rules: { label: 'Scheme rules', source: 'SMAM guidelines (FAISS)', icon: BookOpenText },
}

export const toolMeta = (name: string): ToolMeta =>
  TOOL_META[name] ?? { label: name.replace(/_/g, ' '), source: 'Tool', icon: Question }

export const SUGGESTIONS: { tool: string; text: string }[] = [
  { tool: 'search_inventory', text: 'Which tractors under 9 lakh are in stock?' },
  {
    tool: 'calculate_purchase_plan',
    text: 'Suggest a tractor under 9 lakh with 1 lakh down payment and 40% subsidy. What is the EMI over 5 years?',
  },
  { tool: 'get_weather_forecast', text: 'Is the weather near Dhamtari good for spraying in the next 3 days?' },
  { tool: 'search_service_records', text: 'Show recent service jobs for Ramesh Sahu and what they cost.' },
  { tool: 'check_part_stock', text: 'Is the engine oil filter for the JD 5050D in stock?' },
  { tool: 'estimate_operating_cost', text: 'Diesel cost for running the JD 5050D for 300 hours at Rs 92 per litre?' },
]
