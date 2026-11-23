import { Alert, Box, Button, Card, CardBody, Heading, Text, TextInput } from '@razorpay/blade/components';
import { useState } from 'react';
import { LuCalculator, LuPiggyBank, LuTrendingUp, LuWallet } from 'react-icons/lu';

import { ApiError } from '../api/client';
import type { EstimateRequest, EstimateResponse } from '../api/types';
import { isPercentInput } from '../lib/decimal';
import { formatINR, formatPercent } from '../lib/format';
import { CountUp } from './CountUp';
import { GrowthChart } from './GrowthChart';
import { StatCard } from './StatCard';

const WHOLE_RUPEES = /^\d{1,11}$/;

type Fields = {
  lump: string;
  sip: string;
  years: string;
  regular: string;
  direct: string;
  ret: string;
};

const DEFAULTS: Fields = { lump: '500000', sip: '10000', years: '15', regular: '1.65', direct: '0.70', ret: '12' };

/** "No statement? Estimate in 10 seconds." Every figure shown comes from the engine. */
export function Estimator({ estimate }: { estimate: (req: EstimateRequest) => Promise<EstimateResponse> }) {
  const [f, setF] = useState<Fields>(DEFAULTS);
  const [result, setResult] = useState<EstimateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (key: keyof Fields) => ({ value }: { value?: string }) => {
    setF((prev) => ({ ...prev, [key]: (value ?? '').trim() }));
  };
  const lumpOk = f.lump === '' || WHOLE_RUPEES.test(f.lump);
  const sipOk = f.sip === '' || WHOLE_RUPEES.test(f.sip);
  const yearsOk = /^\d{1,2}$/.test(f.years) && Number(f.years) >= 1 && Number(f.years) <= 40;
  const tersOk = isPercentInput(f.regular) && isPercentInput(f.direct) && Number(f.regular) <= 5;
  const retOk = isPercentInput(f.ret) && Number(f.ret) <= 30;
  const something = (f.lump !== '' && f.lump !== '0') || (f.sip !== '' && f.sip !== '0');
  const valid = lumpOk && sipOk && yearsOk && tersOk && retOk && something;

  const run = async () => {
    if (!valid) return;
    setBusy(true);
    setError(null);
    try {
      setResult(
        await estimate({
          lump_sum: f.lump || '0',
          monthly_sip: f.sip || '0',
          years: Number(f.years),
          ter_regular_percent: f.regular,
          ter_direct_percent: f.direct,
          expected_return_percent: f.ret,
        }),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card padding="spacing.7">
      <CardBody>
        <Box display="flex" flexDirection="column" gap="spacing.6">
          <Box display="flex" alignItems="center" gap="spacing.2">
            <LuCalculator aria-hidden="true" />
            <Heading as="h3" size="medium">
              No statement? Estimate in 10 seconds
            </Heading>
          </Box>
          <form
            aria-label="Commission estimator"
            onSubmit={(e) => {
              e.preventDefault();
              void run();
            }}
          >
            <Box display="flex" flexDirection="column" gap="spacing.4">
              <Box display="grid" gridTemplateColumns={{ base: '1fr', m: 'repeat(3, 1fr)' }} gap="spacing.4">
                <TextInput label="Invested today (₹)" value={f.lump} onChange={set('lump')} validationState={lumpOk ? 'none' : 'error'} errorText="Whole rupees, digits only." />
                <TextInput label="Monthly SIP (₹)" value={f.sip} onChange={set('sip')} validationState={sipOk ? 'none' : 'error'} errorText="Whole rupees, digits only." />
                <TextInput label="Years" value={f.years} onChange={set('years')} validationState={yearsOk ? 'none' : 'error'} errorText="1 to 40 years." />
                <TextInput label="Regular plan TER (%)" value={f.regular} onChange={set('regular')} validationState={tersOk ? 'none' : 'error'} errorText="0 to 5." helpText="On the fund's factsheet" />
                <TextInput label="Direct plan TER (%)" value={f.direct} onChange={set('direct')} validationState={tersOk ? 'none' : 'error'} errorText="0 to 5." />
                <TextInput label="Expected return (%)" value={f.ret} onChange={set('ret')} validationState={retOk ? 'none' : 'error'} errorText="0 to 30." helpText="Yearly, before fees" />
              </Box>
              <Box>
                <Button type="submit" isDisabled={!valid} isLoading={busy}>
                  Estimate my commission
                </Button>
              </Box>
            </Box>
          </form>

          {error ? <Alert color="negative" description={error} isFullWidth /> : null}

          {result ? (
            <Box display="flex" flexDirection="column" gap="spacing.5" aria-live="polite">
              <Heading as="h4" size="large">
                Commission would cost you <CountUp value={result.leak} options={{ compact: true }} /> over{' '}
                {String(result.years)} years.
              </Heading>
              <Text color="surface.text.gray.muted">
                {`That's ${formatPercent(result.leak_share, 1)} of what the same money could grow to in Direct, and ${formatINR(result.first_year_fees_gap)} in extra fees in the first year alone.`}
              </Text>
              <Box display="grid" gridTemplateColumns={{ base: '1fr', m: 'repeat(3, 1fr)' }} gap="spacing.4">
                <StatCard index={0} Icon={LuWallet} label="You invest" value={formatINR(result.invested, { compact: true })} />
                <StatCard index={1} Icon={LuTrendingUp} label="Direct plan grows to" value={formatINR(result.direct_value, { compact: true })} />
                <StatCard index={2} Icon={LuPiggyBank} label="Regular plan grows to" value={formatINR(result.regular_value, { compact: true })} />
              </Box>
              <GrowthChart points={result.series.map((p) => ({ year: p.year, regular: p.regular, direct: p.direct }))} />
              <Text size="small" color="surface.text.gray.muted">
                An estimate, not advice. Upload your statement for a lot-by-lot plan with exact tax.
              </Text>
            </Box>
          ) : null}
        </Box>
      </CardBody>
    </Card>
  );
}
