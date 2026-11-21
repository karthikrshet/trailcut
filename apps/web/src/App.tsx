import { Alert, Box, Heading, Text } from '@razorpay/blade/components';
import { LuShieldCheck } from 'react-icons/lu';

export function App() {
  return (
    <Box
      as="main"
      maxWidth="1120px"
      marginX="auto"
      paddingX="spacing.5"
      paddingY="spacing.10"
      display="flex"
      flexDirection="column"
      gap="spacing.6"
    >
      <Heading as="h1" size="xlarge">
        TrailCut
      </Heading>
      <Text size="large">Cut the commission, not your returns.</Text>
      <Box display="flex" alignItems="center" gap="spacing.3">
        <LuShieldCheck aria-hidden="true" />
        <Text>Your statement is processed in memory and never stored.</Text>
      </Box>
      <Alert
        title="Not investment advice"
        description="TrailCut is a calculator and explainer. It never places orders or names funds to buy."
        color="notice"
        isDismissible={false}
        isFullWidth
      />
    </Box>
  );
}
