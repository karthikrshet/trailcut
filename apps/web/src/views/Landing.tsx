import {
  Accordion,
  AccordionItem,
  AccordionItemBody,
  AccordionItemHeader,
  Badge,
  Box,
  Card,
  CardBody,
  Heading,
  Link,
  Text,
} from '@razorpay/blade/components';
import { motion, useReducedMotionConfig } from 'motion/react';
import type { IconType } from 'react-icons';
import {
  LuArrowRightLeft,
  LuCalculator,
  LuGithub,
  LuPiggyBank,
  LuShieldCheck,
  LuSlidersHorizontal,
  LuSparkles,
  LuUserX,
} from 'react-icons/lu';

import { UploadCard } from '../components/UploadCard';

const FEATURES: { Icon: IconType; title: string; body: string }[] = [
  { Icon: LuPiggyBank, title: 'Commission leak', body: 'What Regular plans cost you this year, and over 10 and 20 years.' },
  { Icon: LuArrowRightLeft, title: 'Lot-by-lot switch plan', body: 'Switch now, wait until a date, or keep, for every purchase.' },
  { Icon: LuCalculator, title: 'Tax and exit load', body: 'STCG, LTCG, the ₹1.25 lakh limit, ELSS lock-in and 2018 grandfathering.' },
  { Icon: LuSlidersHorizontal, title: 'What-if assumptions', body: 'Change return, tax slab and horizon; the plan updates.' },
  { Icon: LuSparkles, title: 'Ask the AI', body: 'Plain-language answers that only quote numbers the calculator produced.' },
  { Icon: LuShieldCheck, title: 'Private by design', body: 'Read in memory, PII masked, nothing stored. Delete anytime.' },
];

const FAQ = [
  {
    q: 'Is this investment advice?',
    a: 'No. TrailCut is a calculator and explainer. It never recommends funds to buy and never places orders.',
  },
  {
    q: 'Is my data stored?',
    a: 'No. Your PDF is read in memory and discarded. The plan lives for 30 minutes, or until you press Delete my data.',
  },
  {
    q: 'Will switching cost me tax?',
    a: 'Sometimes. That is the point of the plan: it shows the exact tax and exit load for each lot, and when waiting makes it cheaper.',
  },
  {
    q: 'Which statements work?',
    a: 'The Detailed CAS from CAMS or KFintech. MF Central, summary and NSDL/CDSL statements are not supported yet.',
  },
];

function Section({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <Box as="section" display="flex" flexDirection="column" gap="spacing.6" paddingY={{ base: 'spacing.9', m: 'spacing.11' }}>
      {title ? (
        <Heading as="h2" size="large">
          {title}
        </Heading>
      ) : null}
      {children}
    </Box>
  );
}

export function Landing({
  onUpload,
  onSample,
  busy,
}: {
  onUpload: (file: File, password: string) => void;
  onSample: () => void;
  busy: boolean;
}) {
  const reduce = useReducedMotionConfig();
  const fade = (i: number) => ({
    initial: reduce ? { opacity: 0 } : { opacity: 0, y: 12 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.32, delay: reduce ? 0 : i * 0.08 },
  });

  return (
    <Box>
      <Box
        display="grid"
        gridTemplateColumns={{ base: '1fr', l: '1.1fr 1fr' }}
        gap="spacing.9"
        alignItems="center"
        paddingY={{ base: 'spacing.8', m: 'spacing.11' }}
      >
        <Box display="flex" flexDirection="column" gap="spacing.5">
          <motion.div {...fade(0)}>
            <Badge color="primary">TrailCut · Open source · Free</Badge>
          </motion.div>
          <motion.div {...fade(1)}>
            <Heading as="h1" size="2xlarge">
              Stop paying commission on your own money.
            </Heading>
          </motion.div>
          <motion.div {...fade(2)}>
            <Text size="large">
              Upload your mutual fund statement. Get a tax-smart plan to switch from Regular to Direct, lot by lot,
              in under a minute.
            </Text>
          </motion.div>
          <motion.div {...fade(3)}>
            <Box display="flex" gap="spacing.5" flexWrap="wrap">
              {[
                { Icon: LuShieldCheck, label: 'Never stored' },
                { Icon: LuUserX, label: 'No login' },
                { Icon: LuGithub, label: 'Open source' },
              ].map(({ Icon, label }) => (
                <Box key={label} display="flex" alignItems="center" gap="spacing.2">
                  <Icon aria-hidden="true" />
                  <Text>{label}</Text>
                </Box>
              ))}
            </Box>
          </motion.div>
        </Box>
        <UploadCard onUpload={onUpload} onSample={onSample} busy={busy} />
      </Box>

      <Section>
        <Text size="large" textAlign="center">
          TrailCut reads your CAS, finds the hidden trail commission, and plans the cheapest way out, without guessing
          a single number.
        </Text>
      </Section>

      <Section title="How it works">
        <Box display="grid" gridTemplateColumns={{ base: '1fr', m: 'repeat(3, 1fr)' }} gap="spacing.5">
          {[
            ['1', 'Download your CAS', 'Request the Detailed CAS from CAMS or KFintech. It is free and takes about two minutes.'],
            ['2', 'Upload it here', 'Add the PDF and its password. It is read in memory and never stored.'],
            ['3', 'Get your plan', 'See what to switch now, what to wait on, and what it all costs. Ask the AI anything.'],
          ].map(([n, title, body]) => (
            <Card key={n} padding="spacing.5">
              <CardBody>
                <Box display="flex" flexDirection="column" gap="spacing.2">
                  <Text weight="semibold">{`${n ?? ''}. ${title ?? ''}`}</Text>
                  <Text color="surface.text.gray.muted">{body}</Text>
                </Box>
              </CardBody>
            </Card>
          ))}
        </Box>
      </Section>

      <Section title="What you get">
        <Box display="grid" gridTemplateColumns={{ base: '1fr', m: 'repeat(2, 1fr)', l: 'repeat(3, 1fr)' }} gap="spacing.5">
          {FEATURES.map(({ Icon, title, body }) => (
            <Card key={title} padding="spacing.5">
              <CardBody>
                <Box display="flex" flexDirection="column" gap="spacing.2">
                  <Box display="flex" alignItems="center" gap="spacing.2">
                    <Icon aria-hidden="true" />
                    <Text weight="semibold">{title}</Text>
                  </Box>
                  <Text color="surface.text.gray.muted">{body}</Text>
                </Box>
              </CardBody>
            </Card>
          ))}
        </Box>
      </Section>

      <Section title="Questions">
        <Accordion>
          {FAQ.map(({ q, a }) => (
            <AccordionItem key={q}>
              <AccordionItemHeader title={q} />
              <AccordionItemBody>
                <Text>{a}</Text>
              </AccordionItemBody>
            </AccordionItem>
          ))}
        </Accordion>
      </Section>

      <Box as="footer" display="flex" flexDirection="column" gap="spacing.3" paddingY="spacing.8">
        <Text size="small" color="surface.text.gray.muted">
          TrailCut is a calculator and explainer, not investment advice. It never places orders or recommends funds
          to buy. Data: AMFI (NAV, expense ratios), casparser (statement parsing, MIT licence).
        </Text>
        <Box display="flex" gap="spacing.5" flexWrap="wrap">
          <Link href="https://github.com/karthikrshet/trailcut" target="_blank" rel="noreferrer">
            GitHub
          </Link>
          <Text size="small" color="surface.text.gray.muted">
            Built by Karthik Rajesh Shet / CodeMyFYP
          </Text>
        </Box>
      </Box>
    </Box>
  );
}
