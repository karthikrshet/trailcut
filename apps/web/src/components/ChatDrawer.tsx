import {
  Alert,
  Box,
  Button,
  Drawer,
  DrawerBody,
  DrawerHeader,
  Spinner,
  Text,
  TextArea,
} from '@razorpay/blade/components';
import { useState } from 'react';
import { LuSend, LuShieldCheck, LuSparkles } from 'react-icons/lu';

import { ApiError } from '../api/client';
import type { ChatResponse, ChatTurn } from '../api/types';
import { SUGGESTIONS } from './chatSuggestions';


type Message = { role: 'user' | 'assistant'; text: string; reply?: ChatResponse };

/** Ask the agent team about this portfolio. Answers only quote calculator figures. */
export function ChatDrawer({
  isOpen,
  onClose,
  ask,
}: {
  isOpen: boolean;
  onClose: () => void;
  ask: (message: string, history: ChatTurn[]) => Promise<ChatResponse>;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showTrace, setShowTrace] = useState<number | null>(null);

  const send = async (text: string) => {
    const question = text.trim();
    if (!question || busy) return;
    const history: ChatTurn[] = messages.slice(-6).map((m) => ({ role: m.role, content: m.text }));
    setMessages((prev) => [...prev, { role: 'user', text: question }]);
    setDraft('');
    setBusy(true);
    setError(null);
    try {
      const reply = await ask(question, history);
      setMessages((prev) => [...prev, { role: 'assistant', text: reply.answer, reply }]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer isOpen={isOpen} onDismiss={onClose} accessibilityLabel="Ask about your portfolio">
      <DrawerHeader title="Ask about your portfolio" subtitle="Answers quote only the calculator's numbers" />
      <DrawerBody>
        <Box display="flex" flexDirection="column" gap="spacing.4">
          {messages.length === 0 ? (
            <Box display="flex" flexDirection="column" gap="spacing.3">
              <Box display="flex" alignItems="center" gap="spacing.2">
                <LuSparkles aria-hidden="true" />
                <Text weight="semibold">Try asking</Text>
              </Box>
              <Box display="flex" flexWrap="wrap" gap="spacing.2">
                {SUGGESTIONS.map((s) => (
                  <Button key={s} size="small" variant="secondary" onClick={() => void send(s)}>
                    {s}
                  </Button>
                ))}
              </Box>
            </Box>
          ) : null}

          <div role="log" aria-live="polite" aria-label="Conversation">
            <Box display="flex" flexDirection="column" gap="spacing.4">
              {messages.map((m, i) => (
                <Box
                  key={i}
                  padding="spacing.4"
                  borderRadius="medium"
                  backgroundColor={m.role === 'user' ? 'surface.background.gray.moderate' : 'surface.background.gray.intense'}
                  borderWidth="thin"
                  borderColor="surface.border.gray.muted"
                >
                  <Text size="small" weight="semibold">
                    {m.role === 'user' ? 'You' : 'TrailCut'}
                  </Text>
                  <Text>{m.text}</Text>
                  {m.reply?.notice ? (
                    <Box display="flex" gap="spacing.2" marginTop="spacing.2">
                      <LuShieldCheck aria-hidden="true" />
                      <Text size="small" color="surface.text.gray.muted">
                        {m.reply.notice}
                      </Text>
                    </Box>
                  ) : null}
                  {m.reply && m.reply.trace.length > 0 ? (
                    <Box marginTop="spacing.2">
                      <Button
                        size="xsmall"
                        variant="tertiary"
                        onClick={() => {
                          setShowTrace(showTrace === i ? null : i);
                        }}
                      >
                        {showTrace === i ? 'Hide how I got this' : 'How I got this'}
                      </Button>
                      {showTrace === i ? (
                        <ol className="plain-list" aria-label="Steps">
                          {m.reply.trace.map((t, j) => (
                            <li key={j}>
                              <Text size="small" color="surface.text.gray.muted">
                                {`${t.kind}: ${t.name}${t.detail ? ` (${t.detail})` : ''}`}
                              </Text>
                            </li>
                          ))}
                        </ol>
                      ) : null}
                    </Box>
                  ) : null}
                </Box>
              ))}
              {busy ? <Spinner accessibilityLabel="Thinking" size="medium" /> : null}
            </Box>
          </div>

          {error ? <Alert color="negative" description={error} isFullWidth /> : null}

          <form
            aria-label="Ask a question"
            onSubmit={(e) => {
              e.preventDefault();
              void send(draft);
            }}
          >
            <Box display="flex" flexDirection="column" gap="spacing.2">
              <TextArea
                label="Your question"
                value={draft}
                maxCharacters={1000}
                numberOfLines={2}
                onChange={({ value }) => {
                  setDraft(value ?? '');
                }}
                placeholder="e.g. Why should I wait on the small cap fund?"
              />
              <Box display="flex" alignItems="center" justifyContent="space-between" gap="spacing.2">
                <Text size="small" color="surface.text.gray.muted">
                  Not investment advice. No funds are recommended.
                </Text>
                <Box display="flex" alignItems="center" gap="spacing.2">
                  <LuSend aria-hidden="true" />
                  <Button type="submit" isDisabled={!draft.trim()} isLoading={busy}>
                    Ask
                  </Button>
                </Box>
              </Box>
            </Box>
          </form>
        </Box>
      </DrawerBody>
    </Drawer>
  );
}
