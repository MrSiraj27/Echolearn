import { TimelineData } from "@/lib/types";

export default function TimelineInfographic({ data }: { data: TimelineData }) {
  return (
    <div className="bg-white text-neutral-900 rounded-xl overflow-hidden">
      <div className="bg-neutral-900 text-white px-6 py-5">
        <h2 className="text-xl font-bold tracking-tight">{data.title}</h2>
      </div>
      <div className="p-6">
        <div className="relative pl-6">
          <div className="absolute left-[7px] top-1 bottom-1 w-px bg-neutral-200" />
          <div className="space-y-6">
            {data.events.map((event, i) => (
              <div key={i} className="relative">
                <div className="absolute -left-6 top-1 h-3.5 w-3.5 rounded-full bg-neutral-900 ring-4 ring-white" />
                <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide">
                  {event.date_or_stage}
                </p>
                <p className="text-sm font-semibold text-neutral-900 mt-0.5">{event.label}</p>
                <p className="text-sm text-neutral-500 mt-0.5 leading-relaxed">{event.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
