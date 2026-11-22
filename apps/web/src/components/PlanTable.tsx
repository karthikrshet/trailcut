import {
  Accordion,
  AccordionItem,
  AccordionItemBody,
  AccordionItemHeader,
  Box,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableHeaderRow,
  TableRow,
  Text,
} from '@razorpay/blade/components';

import type { LotDecision, SchemePlan } from '../api/types';
import { formatDate, formatINR } from '../lib/format';
import { schemeSummary } from './actionMeta';
import { StatusBadge } from './StatusBadge';

function when(d: LotDecision): string {
  if (d.action === 'wait' && d.switch_on) return `until ${formatDate(d.switch_on)}`;
  return '';
}

type Row = LotDecision & { id: string };

/** One expandable section per fund; each lot row says what to do and why. */
export function PlanTable({ schemes, decisions }: { schemes: SchemePlan[]; decisions: LotDecision[] }) {
  return (
    <Accordion>
      {schemes.map((scheme) => {
        const rows: Row[] = decisions
          .filter((d) => d.scheme_id === scheme.scheme_id)
          .map((d) => ({ ...d, id: d.lot_id }));
        return (
          <AccordionItem key={scheme.scheme_id}>
            <AccordionItemHeader title={scheme.name} subtitle={schemeSummary(scheme)} />
            <AccordionItemBody>
            {rows.length === 0 ? (
              <Text color="surface.text.gray.muted">No units held in this fund.</Text>
            ) : (
              <Box overflowX="auto">
                <Table data={{ nodes: rows }}>
                  {(items) => (
                    <>
                      <TableHeader>
                        <TableHeaderRow>
                          <TableHeaderCell>Bought</TableHeaderCell>
                          <TableHeaderCell>Value</TableHeaderCell>
                          <TableHeaderCell>Do this</TableHeaderCell>
                          <TableHeaderCell>Tax</TableHeaderCell>
                          <TableHeaderCell>Exit load</TableHeaderCell>
                          <TableHeaderCell>Why</TableHeaderCell>
                        </TableHeaderRow>
                      </TableHeader>
                      <TableBody>
                        {items.map((d) => (
                          <TableRow key={d.id} item={d}>
                            <TableCell>{formatDate(d.buy_date)}</TableCell>
                            <TableCell>{formatINR(d.value_now)}</TableCell>
                            <TableCell>
                              <StatusBadge action={d.action} suffix={when(d)} />
                            </TableCell>
                            <TableCell>{d.switch_on ? formatINR(d.tax) : '—'}</TableCell>
                            <TableCell>{d.switch_on ? formatINR(d.exit_load) : '—'}</TableCell>
                            <TableCell>
                              <Text size="small">{d.explanation}</Text>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </>
                  )}
                </Table>
              </Box>
            )}
            </AccordionItemBody>
          </AccordionItem>
        );
      })}
    </Accordion>
  );
}
