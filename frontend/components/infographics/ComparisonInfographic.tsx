import { ComparisonData } from "@/lib/types";

export default function ComparisonInfographic({ data }: { data: ComparisonData }) {
  return (
    <div className="bg-white text-neutral-900 rounded-xl overflow-hidden">
      <div className="bg-neutral-900 text-white px-6 py-5">
        <h2 className="text-xl font-bold tracking-tight">{data.title}</h2>
      </div>
      <div className="p-6">
        <div className="grid grid-cols-[1fr_auto_1fr] gap-2 mb-1">
          <div />
          <div />
          <div />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr>
                <th className="text-left font-medium text-neutral-400 text-xs uppercase tracking-wide pb-2 pr-2 w-1/3">
                  Aspect
                </th>
                <th className="text-left font-bold text-neutral-900 pb-2 px-2 border-b-2 border-amber-500">
                  {data.item_a_name}
                </th>
                <th className="text-left font-bold text-neutral-900 pb-2 px-2 border-b-2 border-neutral-900">
                  {data.item_b_name}
                </th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row, i) => (
                <tr key={i} className="border-b border-neutral-100 last:border-0">
                  <td className="py-2.5 pr-2 text-xs font-medium text-neutral-500">{row.aspect}</td>
                  <td className="py-2.5 px-2 text-neutral-800">{row.item_a_value}</td>
                  <td className="py-2.5 px-2 text-neutral-800">{row.item_b_value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {data.verdict && (
        <div className="mx-6 mb-6 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
          <p className="text-sm text-amber-900">{data.verdict}</p>
        </div>
      )}
    </div>
  );
}
