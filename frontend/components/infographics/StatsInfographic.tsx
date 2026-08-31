import { DollarSign, Users, Clock, TrendingUp, Info, LucideIcon } from "lucide-react";
import { StatsData } from "@/lib/types";

const ICONS: Record<string, LucideIcon> = {
  money: DollarSign,
  users: Users,
  time: Clock,
  growth: TrendingUp,
  default: Info,
};

export default function StatsInfographic({ data }: { data: StatsData }) {
  return (
    <div className="bg-white text-neutral-900 rounded-xl overflow-hidden">
      <div className="bg-neutral-900 text-white px-6 py-5">
        <h2 className="text-xl font-bold tracking-tight">{data.title}</h2>
        {data.subtitle && <p className="text-sm text-neutral-300 mt-1">{data.subtitle}</p>}
      </div>
      <div className="p-6 grid grid-cols-2 sm:grid-cols-3 gap-3">
        {data.stats.map((stat, i) => {
          const Icon = ICONS[stat.icon_hint] || ICONS.default;
          return (
            <div key={i} className="rounded-xl border border-neutral-200 bg-neutral-50 p-4 flex flex-col gap-2">
              <Icon className="h-4 w-4 text-neutral-500" />
              <p className="text-2xl font-bold tracking-tight text-neutral-900">{stat.value}</p>
              <p className="text-xs font-medium text-neutral-500 leading-snug">{stat.label}</p>
            </div>
          );
        })}
      </div>
      {data.takeaway && (
        <div className="mx-6 mb-6 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
          <p className="text-sm text-amber-900">{data.takeaway}</p>
        </div>
      )}
    </div>
  );
}
