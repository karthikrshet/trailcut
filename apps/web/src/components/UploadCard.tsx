import {
  Box,
  Button,
  Card,
  CardBody,
  Checkbox,
  FileUpload,
  PasswordInput,
  Text,
} from '@razorpay/blade/components';
import { useState } from 'react';
import { LuFileLock2 } from 'react-icons/lu';

const MAX_BYTES = 10 * 1024 * 1024;

export function UploadCard({
  onUpload,
  onSample,
  busy,
}: {
  onUpload: (file: File, password: string) => void;
  onSample: () => void;
  busy: boolean;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState('');
  const [consent, setConsent] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const pick = (files: File[]) => {
    const f = files[0] ?? null;
    if (f && f.size >= MAX_BYTES) {
      setProblem('That file is 10 MB or larger. A CAS statement is usually under 2 MB.');
      setFile(null);
      return;
    }
    if (f && !/\.pdf$/i.test(f.name) && f.type !== 'application/pdf') {
      setProblem('Please choose the PDF statement you received from CAMS or KFintech.');
      setFile(null);
      return;
    }
    setProblem(null);
    setFile(f);
  };

  return (
    <Card padding="spacing.7">
      <CardBody>
        <form
          aria-label="Upload your CAS statement"
          onSubmit={(e) => {
            e.preventDefault();
            if (file && consent) onUpload(file, password);
          }}
        >
        <Box display="flex" flexDirection="column" gap="spacing.5">
          <Box display="flex" alignItems="center" gap="spacing.2">
            <LuFileLock2 aria-hidden="true" />
            <Text weight="semibold">Upload your CAS statement</Text>
          </Box>
          <FileUpload
            label="CAMS or KFintech Detailed CAS (PDF)"
            accept=".pdf,application/pdf"
            uploadType="single"
            onChange={({ fileList }) => {
              pick(fileList);
            }}
            validationState={problem ? 'error' : 'none'}
            {...(problem ? { errorText: problem } : {})}
            helpText="Under 10 MB. Read in memory, never stored."
          />
          <PasswordInput
            label="PDF password"
            value={password}
            onChange={({ value }) => {
              setPassword(value ?? '');
            }}
            helpText="The password you set when requesting the CAS (often your PAN in capitals)."
          />
          <Checkbox
            isChecked={consent}
            onChange={({ isChecked }) => {
              setConsent(isChecked);
            }}
          >
            I agree to let TrailCut read this statement in memory to build my plan. Nothing is stored.
          </Checkbox>
          <Box display="flex" gap="spacing.3" flexWrap="wrap">
            <Button type="submit" isDisabled={!file || !consent} isLoading={busy}>
              Check my portfolio
            </Button>
            <Button variant="secondary" onClick={onSample} isDisabled={busy}>
              Try a sample
            </Button>
          </Box>
        </Box>
        </form>
      </CardBody>
    </Card>
  );
}
