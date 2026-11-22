import { Alert, Box, Heading, Switch, Text } from '@razorpay/blade/components';
import { useState } from 'react';
import { LuArrowRightLeft, LuCalculator, LuClock, LuPiggyBank } from 'react-icons/lu';

import type { AssumptionsUpdate, SwitchPlan, Totals } from '../api/types';
import { AssumptionsPanel } from '../components/AssumptionsPanel';
import { PlanTable } from '../components/PlanTable';
import { StatCard } from '../components/StatCard';
import { EmptyBlock } from '../components/StateViews';
import { TerEntry } from '../components/TerEntry';
import { Timeline } from '../components/Timeline';
import { formatINR, formatMonths } from '../lib/format';

function TotalsRow({ totals, horizon }: { totals: Totals; horizon: number }) {
  return (
    <Box display="grid" gridTemplateColumns={{ base: '1fr', s: '1fr 1fr', l: 'repeat(4, 1fr)' }} gap="spacing.4">
      <StatCard index={0} Icon={LuCalculator} label="Total tax" value={formatINR(totals.tax)} />
      <StatCard index={1} Icon={LuArrowRightLeft} label="Total exit load" value={formatINR(totals.exit_load)} />
      <StatCard
        index={2}
        Icon={LuPiggyBank}
        label={`Net benefit over ${String(horizon)} years`}
        value={formatINR(totals.net_benefit, { compact: true })}
      />
      <StatCard
        index={3}
        Icon={LuClock}
        label="Break-even"
        value={totals.break_even_months === null ? '—' : formatMonths(totals.break_even_months)}
        hint="Time for lower fees to repay the switch cost"
      />
    </Box>
  );
}

export function PlanView({
  plan,
  busy,
  updateError,
  onUpdate,
}: {
  plan: SwitchPlan;
  busy: boolean;
  updateError: string | null;
  onUpdate: (u: AssumptionsUpdate) => void;
}) {
  const [compare, setCompare] = useState(false);
  const review = plan.schemes
    .filter((s) => (s.actions.review ?? 0) > 0 && plan.decisions.some((d) => d.scheme_id === s.scheme_id && d.reason === 'no_ter_data'))
    .map((s) => ({ scheme_id: s.scheme_id, name: s.name }));
  const totals = compare ? plan.switch_all_now : plan.totals;

  if (plan.decisions.length === 0) {
    return <EmptyBlock title="Nothing to plan.">This statement has no units left in any fund.</EmptyBlock>;
  }

  return (
    <Box display="flex" flexDirection="column" gap="spacing.8">
      {updateError ? <Alert color="negative" title="Couldn't update the plan" description={updateError} isFullWidth /> : null}

      <Box display="flex" flexDirection="column" gap="spacing.4">
        <Box display="flex" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap="spacing.3">
          <Heading as="h2" size="large">
            {compare ? 'If you switched everything today' : 'Your switch plan'}
          </Heading>
          <Box display="flex" alignItems="center" gap="spacing.3">
            <Switch
              accessibilityLabel="Compare with switching everything today"
              isChecked={compare}
              onChange={({ isChecked }) => {
                setCompare(isChecked);
              }}
            />
            <Text>Compare with switch-all-now</Text>
          </Box>
        </Box>
        <TotalsRow totals={totals} horizon={plan.assumptions.horizon_years} />
        {compare ? (
          <Text color="surface.text.gray.muted">
            {`The plan nets ${formatINR(plan.totals.net_benefit)}; switching everything eligible today nets ${formatINR(plan.switch_all_now.net_benefit)}.`}
          </Text>
        ) : null}
      </Box>

      <Box display="flex" flexDirection="column" gap="spacing.3">
        <Heading as="h3" size="medium">
          When to switch
        </Heading>
        {plan.timeline.length ? <Timeline steps={plan.timeline} /> : <Text>No switches are worth making right now.</Text>}
      </Box>

      <TerEntry funds={review} busy={busy} onApply={onUpdate} />

      <Box display="flex" flexDirection="column" gap="spacing.3">
        <Heading as="h3" size="medium">
          Lot by lot
        </Heading>
        <PlanTable schemes={plan.schemes} decisions={plan.decisions} />
      </Box>

      <AssumptionsPanel key={JSON.stringify(plan.assumptions)} assumptions={plan.assumptions} busy={busy} onApply={onUpdate} />

      {plan.notes.length ? (
        <Box as="aside" display="flex" flexDirection="column" gap="spacing.2">
          {plan.notes.map((n) => (
            <Text key={n} size="small" color="surface.text.gray.muted">
              {n}
            </Text>
          ))}
        </Box>
      ) : null}
    </Box>
  );
}
