import { Alert, Box, Button, Tabs, TabItem, TabList, TabPanel, Text } from '@razorpay/blade/components';
import { useState } from 'react';

import type { AssumptionsUpdate, SessionResponse } from '../api/types';
import { PlanView } from './PlanView';
import { ReportView } from './ReportView';

export function Workspace({
  data,
  busy,
  updateError,
  onUpdate,
  onDelete,
  chat,
}: {
  data: SessionResponse;
  busy: boolean;
  updateError: string | null;
  onUpdate: (u: AssumptionsUpdate) => void;
  onDelete: () => void;
  chat?: React.ReactNode;
}) {
  const [tab, setTab] = useState('report');
  return (
    <Box display="flex" flexDirection="column" gap="spacing.6" paddingY="spacing.6">
      <Box display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap="spacing.3">
        <Text color="surface.text.gray.muted">
          {data.is_sample ? 'Sample portfolio (fictional)' : 'Your portfolio'}
        </Text>
        <Box display="flex" gap="spacing.3">
          {chat}
          <Button variant="secondary" color="negative" onClick={onDelete}>
            Delete my data
          </Button>
        </Box>
      </Box>
      {data.notes.map((n) => (
        <Alert key={n} color="information" description={n} isDismissible={false} isFullWidth />
      ))}
      <Tabs
        value={tab}
        onChange={(v) => {
          setTab(v);
        }}
      >
        <TabList>
          <TabItem value="report">Report</TabItem>
          <TabItem value="plan">Switch plan</TabItem>
        </TabList>
        <TabPanel value="report">
          <Box paddingY="spacing.6">
            <ReportView report={data.report} />
          </Box>
        </TabPanel>
        <TabPanel value="plan">
          <Box paddingY="spacing.6">
            <PlanView plan={data.plan} busy={busy} updateError={updateError} onUpdate={onUpdate} />
          </Box>
        </TabPanel>
      </Tabs>
      <Alert color="notice" title="Not investment advice" description={data.disclaimer} isDismissible={false} isFullWidth />
    </Box>
  );
}
