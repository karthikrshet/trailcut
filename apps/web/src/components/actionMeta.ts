import type { IconType } from 'react-icons';
import { LuCircleCheck, LuHourglass, LuMinus, LuTriangleAlert } from 'react-icons/lu';

import type { Action, SchemePlan } from '../api/types';

type Meta = { label: string; color: 'positive' | 'notice' | 'neutral' | 'information'; Icon: IconType };

export const ACTION_META: Record<Action, Meta> = {
  switch_now: { label: 'Switch now', color: 'positive', Icon: LuCircleCheck },
  wait: { label: 'Wait', color: 'notice', Icon: LuHourglass },
  keep: { label: 'Keep', color: 'neutral', Icon: LuMinus },
  review: { label: 'Review', color: 'information', Icon: LuTriangleAlert },
};

const ORDER: Action[] = ['switch_now', 'wait', 'keep', 'review'];

/** "3 switch now · 1 wait" for a fund's lots. */
export function schemeSummary(scheme: SchemePlan): string {
  const parts = ORDER.filter((a) => (scheme.actions[a] ?? 0) > 0).map(
    (a) => `${String(scheme.actions[a])} ${ACTION_META[a].label.toLowerCase()}`,
  );
  return parts.length ? parts.join(' · ') : 'No units held';
}
