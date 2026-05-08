"use client";

interface Source {
  title: string;
  category: string;
  filename?: string;
}

export function SourceList({ sources }: { sources: Source[] }) {
  if (!sources?.length) return null;
  return (
    <div className="mt-2 border-t border-gray-200 pt-2">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Sources</p>
      <ul className="space-y-1">
        {sources.map((s, i) => (
          <li key={i} className="text-xs text-gray-600 flex items-start gap-1">
            <span className="inline-block bg-blue-100 text-blue-700 rounded px-1">{s.category}</span>
            <span>{s.title}</span>
            {s.filename && <span className="text-gray-400">({s.filename})</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}
