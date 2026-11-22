import { Box, Button, Heading, Radio, RadioGroup, Switch, Text, TextInput } from '@razorpay/blade/components';
import { useState } from 'react';
import { LuSlidersHorizontal } from 'react-icons/lu';

import type { Assumptions, AssumptionsUpdate } from '../api/types';
import { fractionToPercent, isPercentInput, percentToFraction } from '../lib/decimal';

const SLABS = ['0', '5', '10', '15', '20', '30'];

/** Every planning assumption is visible and editable. */
export function AssumptionsPanel({
  assumptions,
  busy,
  onApply,
}: {
  assumptions: Assumptions;
  busy: boolean;
  onApply: (update: AssumptionsUpdate) => void;
}) {
  const [ret, setRet] = useState(fractionToPercent(assumptions.expected_return));
  const [slab, setSlab] = useState(fractionToPercent(assumptions.slab_rate));
  const [horizon, setHorizon] = useState(String(assumptions.horizon_years));
  const [nextFy, setNextFy] = useState(assumptions.use_next_fy_exemption);

  const retOk = isPercentInput(ret) && Number(ret) <= 50;
  const horizonOk = /^\d{1,2}$/.test(horizon) && Number(horizon) >= 1 && Number(horizon) <= 40;
  const valid = retOk && horizonOk && SLABS.includes(slab);

  const apply = () => {
    const expected = percentToFraction(ret);
    const slabRate = percentToFraction(slab);
    if (!valid || expected === null || slabRate === null) return;
    onApply({
      expected_return: expected,
      slab_rate: slabRate,
      horizon_years: Number(horizon),
      use_next_fy_exemption: nextFy,
    });
  };

  return (
    <section aria-label="Assumptions">
    <Box display="flex" flexDirection="column" gap="spacing.4">
      <Box display="flex" alignItems="center" gap="spacing.2">
        <LuSlidersHorizontal aria-hidden="true" />
        <Heading as="h3" size="small">
          Assumptions
        </Heading>
      </Box>
      <Box display="grid" gridTemplateColumns={{ base: '1fr', m: '1fr 1fr 1fr' }} gap="spacing.4">
        <TextInput
          label="Expected yearly return (%)"
          value={ret}
          onChange={({ value }) => {
            setRet(value ?? '');
          }}
          validationState={retOk ? 'none' : 'error'}
          errorText="Enter a number between 0 and 50."
          helpText="Before fees. Used for every projection."
        />
        <RadioGroup
          label="Income-tax slab (%)"
          name="slab"
          value={slab}
          helpText="For debt-fund gains taxed at your slab."
          onChange={({ value }) => {
            setSlab(value);
          }}
        >
          <Box display="flex" gap="spacing.4" flexWrap="wrap">
            {SLABS.map((s) => (
              <Radio key={s} value={s}>
                {`${s}%`}
              </Radio>
            ))}
          </Box>
        </RadioGroup>
        <TextInput
          label="Planning horizon (years)"
          value={horizon}
          onChange={({ value }) => {
            setHorizon(value ?? '');
          }}
          validationState={horizonOk ? 'none' : 'error'}
          errorText="Enter 1 to 40 years."
        />
      </Box>
      <Box display="flex" alignItems="center" gap="spacing.3">
        <Switch
          accessibilityLabel="Allow waiting until 1 April to use next year's tax-free limit"
          isChecked={nextFy}
          onChange={({ isChecked }) => {
            setNextFy(isChecked);
          }}
        />
        <Text>Allow waiting until 1 April to use next year&apos;s ₹1.25 lakh tax-free limit</Text>
      </Box>
      <Box>
        <Button onClick={apply} isDisabled={!valid} isLoading={busy}>
          Update plan
        </Button>
      </Box>
    </Box>
    </section>
  );
}
