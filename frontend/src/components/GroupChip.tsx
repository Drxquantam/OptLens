import { GROUP_LETTERS, GROUP_STYLES } from '../lib/format';

export function GroupChip({ group }: { group: number | null }) {
  if (group == null) return <span className="text-faint">–</span>;
  return (
    <span
      className={`inline-flex h-5 w-5 items-center justify-center rounded-md border font-mono text-[11px] font-semibold ${GROUP_STYLES[group] ?? GROUP_STYLES[4]}`}
      title={`Behaviour group ${GROUP_LETTERS[group]}: builds with the same letter behaved identically`}
    >
      {GROUP_LETTERS[group] ?? '?'}
    </span>
  );
}
