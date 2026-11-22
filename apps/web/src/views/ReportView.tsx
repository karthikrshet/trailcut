import {
  Box,
  Heading,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableHeaderRow,
  TableRow,
  Text,
} from '@razorpay/blade/components';
import { LuPiggyBank, LuTrendingUp, LuTriangleAlert, LuWallet } from 'react-icons/lu';

import type { Report, SchemeLeak } from '../api/types';
import { CountUp } from '../components/CountUp';
import { GrowthChart } from '../components/GrowthChart';
import { StatCard } from '../components/StatCard';
import { EmptyBlock } from '../components/StateViews';
import { formatINR, formatPercent } from '../lib/format';

type Row = SchemeLeak & { id: string };

export function ReportView({ report }: { report: Report }) {
  const s = report.summary;
  if (s.schemes.length === 0) {
    return <EmptyBlock title="No funds found in this statement.">Check that you uploaded the Detailed CAS.</EmptyBlock>;
  }
  const hasLeak = report.yearly_leak !== '0.00' && report.yearly_leak !== '0';
  const rows: Row[] = report.leaks.map((l) => ({ ...l, id: l.scheme_id }));

  return (
    <Box display="flex" flexDirection="column" gap="spacing.8">
      <Box display="grid" gridTemplateColumns={{ base: '1fr', s: '1fr 1fr', l: 'repeat(4, 1fr)' }} gap="spacing.4">
        <StatCard index={0} Icon={LuWallet} label="Current value" value={formatINR(s.value, { compact: true })} hint={`Invested ${formatINR(s.invested, { compact: true })}`} />
        <StatCard index={1} Icon={LuTrendingUp} label="Your return (XIRR)" value={s.xirr ? formatPercent(s.xirr) : '—'} hint={s.xirr ? 'A year, all funds together' : 'Needs full purchase history'} />
        <StatCard index={2} Icon={LuPiggyBank} label="Commission this year" value={formatINR(report.yearly_leak, { compact: true })} hint="Extra fees in Regular plans" />
        <StatCard index={3} Icon={LuTriangleAlert} label="20-year cost" value={formatINR(report.leak_20y, { compact: true })} hint={`At ${formatPercent(report.expected_return, 0)} a year before fees`} />
      </Box>

      <Box display="flex" flexDirection="column" gap="spacing.4">
        {hasLeak ? (
          <Heading as="h2" size="xlarge">
            You&apos;ll pay <CountUp value={report.leak_20y} options={{ compact: true }} /> in extra costs over 20 years.
          </Heading>
        ) : (
          <Heading as="h2" size="xlarge">
            No Regular-plan commission found in funds we have data for.
          </Heading>
        )}
        <Text color="surface.text.gray.muted">
          {`${formatPercent(report.regular_share, 0)} of your money is in Regular plans.`}
        </Text>
        <GrowthChart points={report.growth} />
      </Box>

      <Box display="flex" flexDirection="column" gap="spacing.4">
        <Heading as="h3" size="medium">
          By fund
        </Heading>
        <Box overflowX="auto">
          <Table data={{ nodes: rows }}>
            {(items) => (
              <>
                <TableHeader>
                  <TableHeaderRow>
                    <TableHeaderCell>Fund</TableHeaderCell>
                    <TableHeaderCell>Value</TableHeaderCell>
                    <TableHeaderCell>Expense ratio (Regular → Direct)</TableHeaderCell>
                    <TableHeaderCell>Commission a year</TableHeaderCell>
                    <TableHeaderCell>20-year cost</TableHeaderCell>
                  </TableHeaderRow>
                </TableHeader>
                <TableBody>
                  {items.map((l) => (
                    <TableRow key={l.id} item={l}>
                      <TableCell>{l.name}</TableCell>
                      <TableCell>{formatINR(l.value)}</TableCell>
                      <TableCell>
                        {l.plan === 'direct'
                          ? 'Already Direct'
                          : l.ter_regular && l.ter_direct
                            ? `${formatPercent(l.ter_regular)} → ${formatPercent(l.ter_direct)}`
                            : 'Not available'}
                      </TableCell>
                      <TableCell>{l.yearly_leak ? formatINR(l.yearly_leak) : '—'}</TableCell>
                      <TableCell>{l.leak_20y ? formatINR(l.leak_20y) : '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </>
            )}
          </Table>
        </Box>
      </Box>
    </Box>
  );
}
