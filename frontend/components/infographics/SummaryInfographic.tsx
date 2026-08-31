import { SummaryData } from "@/lib/types";

export default function SummaryInfographic({ data }: { data: SummaryData }) {
  return (
    <div className="bg-white text-neutral-900 rounded-xl overflow-hidden">
      <div className="bg-neutral-900 text-white px-6 py-5">
        <h2 className="text-xl font-bold tracking-tight">{data.title}</h2>
      </div>
      <div className="p-6 space-y-3">
        {data.key_points.map((point, i) => (
          <div key={i} className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
            <p className="text-sm font-semibold text-neutral-900">{point.heading}</p>
            <p className="text-sm text-neutral-500 mt-1 leading-relaxed">{point.detail}</p>
          </div>
        ))}
      </div>
      {data.takeaway && (
        <div className="mx-6 mb-6 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
          <p className="text-sm text-amber-900">{data.takeaway}</p>
        </div>
      )}
    </div>
  );
}
