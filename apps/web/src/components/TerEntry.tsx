import { Alert, Box, Button, Text, TextInput } from '@razorpay/blade/components';
import { useState } from 'react';

import type { AssumptionsUpdate } from '../api/types';
import { isPercentInput } from '../lib/decimal';

type Fund = { scheme_id: string; name: string };
type Entry = { regular: string; direct: string };

const valid = (e: Entry | undefined) =>
  !!e && isPercentInput(e.regular) && isPercentInput(e.direct) && Number(e.regular) <= 10 && Number(e.direct) <= 10;

/** Funds without expense-ratio data: ask the user instead of guessing. */
export function TerEntry({
  funds,
  busy,
  onApply,
}: {
  funds: Fund[];
  busy: boolean;
  onApply: (update: AssumptionsUpdate) => void;
}) {
  const [entries, setEntries] = useState<Record<string, Entry>>({});
  if (funds.length === 0) return null;
  const ready = funds.filter((f) => valid(entries[f.scheme_id]));
  const set = (id: string, key: keyof Entry, value: string) => {
    setEntries((prev) => ({ ...prev, [id]: { regular: '', direct: '', ...prev[id], [key]: value } }));
  };

  return (
    <Box display="flex" flexDirection="column" gap="spacing.4">
      <Alert
        color="information"
        isDismissible={false}
        isFullWidth
        title="We need two numbers for some funds"
        description="We don't have expense ratios for these funds yet. You'll find both on each fund's factsheet (Regular plan and Direct plan TER)."
      />
      {funds.map((f) => (
        <Box key={f.scheme_id} display="flex" flexDirection="column" gap="spacing.2">
          <Text weight="semibold">{f.name}</Text>
          <Box display="grid" gridTemplateColumns={{ base: '1fr', m: '1fr 1fr' }} gap="spacing.3">
            <TextInput
              label="Regular plan TER (%)"
              placeholder="e.g. 1.65"
              value={entries[f.scheme_id]?.regular ?? ''}
              onChange={({ value }) => {
                set(f.scheme_id, 'regular', value ?? '');
              }}
            />
            <TextInput
              label="Direct plan TER (%)"
              placeholder="e.g. 0.70"
              value={entries[f.scheme_id]?.direct ?? ''}
              onChange={({ value }) => {
                set(f.scheme_id, 'direct', value ?? '');
              }}
            />
          </Box>
        </Box>
      ))}
      <Box>
        <Button
          isDisabled={ready.length === 0}
          isLoading={busy}
          onClick={() => {
            onApply({
              ter_overrides: Object.fromEntries(
                ready.map((f) => {
                  const e = entries[f.scheme_id] as Entry;
                  return [f.scheme_id, { regular_percent: e.regular.trim(), direct_percent: e.direct.trim() }];
                }),
              ),
            });
          }}
        >
          Use these expense ratios
        </Button>
      </Box>
    </Box>
  );
}
