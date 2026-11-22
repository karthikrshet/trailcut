import { Box, Text } from '@razorpay/blade/components';
import { useMemo } from 'react';

import { createClient, type Client } from './api/client';
import { ProcessingSteps } from './components/ProcessingSteps';
import { ErrorBlock } from './components/StateViews';
import { useSession } from './state/useSession';
import { Landing } from './views/Landing';
import { Workspace } from './views/Workspace';

const ERROR_TITLES: Record<string, string> = {
  mf_central_statement: 'This looks like an MF Central statement',
  summary_statement: 'This is a Summary statement',
  depository_statement: 'This is a depository statement',
  wrong_password: "That password didn't work",
  session_expired: 'Your session has ended',
  network_error: "We couldn't connect",
  rate_limited: 'Too many tries',
};

export function App({ client }: { client?: Client }) {
  const api = useMemo(() => client ?? createClient(), [client]);
  const { state, startSample, upload, update, deleteData, reset } = useSession(api);

  return (
    <Box minHeight="100vh" backgroundColor="surface.background.gray.subtle">
      <Box as="header" paddingX={{ base: 'spacing.5', m: 'spacing.8' }} paddingY="spacing.4">
        <Box maxWidth="1120px" marginX="auto" display="flex" justifyContent="space-between" alignItems="center">
          <Text weight="semibold" size="large">
            TrailCut
          </Text>
          <Text size="small" color="surface.text.gray.muted">
            Cut the commission, not your returns.
          </Text>
        </Box>
      </Box>
      <Box as="main" maxWidth="1120px" marginX="auto" paddingX={{ base: 'spacing.5', m: 'spacing.8' }}>
        {state.status === 'idle' ? (
          <Landing onUpload={(f, p) => void upload(f, p)} onSample={() => void startSample()} busy={false} />
        ) : null}
        {state.status === 'loading' ? (
          <Box paddingY="spacing.11" maxWidth="480px" marginX="auto">
            <ProcessingSteps step={state.step} kind={state.kind} />
          </Box>
        ) : null}
        {state.status === 'error' ? (
          <Box paddingY="spacing.11" maxWidth="640px" marginX="auto">
            <ErrorBlock
              title={ERROR_TITLES[state.code] ?? "We couldn't read this statement"}
              message={state.message}
              actionLabel="Start again"
              onAction={reset}
            />
          </Box>
        ) : null}
        {state.status === 'ready' ? (
          <Workspace
            data={state.data}
            busy={state.updating}
            updateError={state.updateError}
            onUpdate={(u) => void update(u)}
            onDelete={() => void deleteData()}
          />
        ) : null}
      </Box>
    </Box>
  );
}
