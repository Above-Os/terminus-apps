import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const root = process.argv[2] || '/app';
function replaceOnce(file, before, after) {
  const path = join(root, file);
  const raw = readFileSync(path, 'utf8');
  const crlf = raw.includes('\r\n');
  const source = raw.replace(/\r\n/g, '\n');
  const needle = before.replace(/\r\n/g, '\n');
  const replacement = after.replace(/\r\n/g, '\n');
  if (source.split(needle).length !== 2) throw new Error(`Upstream patch context changed: ${file}`);
  const next = source.replace(needle, replacement);
  writeFileSync(path, crlf ? next.replace(/\n/g, '\r\n') : next);
}

writeFileSync(join(root, 'apps/web/src/components/openActivationUrl.ts'), `let pending: Window | null = null;
const revealed = new Set<string>();

export function armActivationPopup(): void {
  if (typeof window === 'undefined') return;
  try {
    const popup = window.open('about:blank', '_blank');
    pending = popup && !popup.closed ? popup : null;
  } catch {
    pending = null;
  }
}

function assignHere(url: string): void {
  try {
    window.location.assign(url);
  } catch {
    // The activation link stays copyable.
  }
}

export function revealActivationUrl(url: string): void {
  if (typeof window === 'undefined' || !url || revealed.has(url)) return;
  revealed.add(url);
  if (pending && !pending.closed) {
    try {
      pending.location.href = url;
      pending = null;
      return;
    } catch {
      pending = null;
    }
  }
  let popup: Window | null = null;
  try {
    popup = window.open(url, '_blank');
  } catch {
    popup = null;
  }
  if (popup) return;
  assignHere(url);
}

export function openActivationUrlFromClick(url: string): void {
  if (typeof window === 'undefined' || !url) return;
  if (pending && !pending.closed) {
    try {
      pending.location.href = url;
      pending = null;
      revealed.add(url);
      return;
    } catch {
      pending = null;
    }
  }
  let popup: Window | null = null;
  try {
    popup = window.open(url, '_blank');
  } catch {
    popup = null;
  }
  if (popup) {
    revealed.add(url);
    return;
  }
  revealed.add(url);
  assignHere(url);
}
`);

replaceOnce('apps/web/src/components/EntryShell.tsx',
  `import { closeAmrActivationWindowBestEffort } from './AmrLoginPill';`,
  `import { closeAmrActivationWindowBestEffort } from './AmrLoginPill';
import { armActivationPopup, openActivationUrlFromClick, revealActivationUrl } from './openActivationUrl';`);
replaceOnce('apps/web/src/components/EntryShell.tsx',
  `  async function handleAmrSignInToContinue(`,
  `  useEffect(() => {
    const url = amrStatus?.activationUrl;
    if (url) revealActivationUrl(url);
  }, [amrStatus?.activationUrl]);

  async function handleAmrSignInToContinue(`);
replaceOnce('apps/web/src/components/EntryShell.tsx',
  `    if (amrLoginBusy || amrLoginCancelPending) return;
    amrLoginPollCancelledRef.current = false;`,
  `    if (amrLoginBusy || amrLoginCancelPending) return;
    armActivationPopup();
    amrLoginPollCancelledRef.current = false;`);
replaceOnce('apps/web/src/components/EntryShell.tsx',
  `                      <a
                        className="onboarding-cloud__activation-link"
                        href={amrStatus.activationUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                      >`,
  `                      <a
                        className="onboarding-cloud__activation-link"
                        href={amrStatus.activationUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(event) => {
                          event.preventDefault();
                          openActivationUrlFromClick(amrStatus.activationUrl!);
                        }}
                      >`);

replaceOnce('apps/web/src/components/use-cloud-sign-in.ts',
  `import {
  notifyTeamProjectsChanged,`,
  `import { armActivationPopup, revealActivationUrl } from './openActivationUrl';
import {
  notifyTeamProjectsChanged,`);
replaceOnce('apps/web/src/components/use-cloud-sign-in.ts',
  `  }, []);

  async function begin() {
    if (state === 'signing') return;`,
  `  }, []);

  useEffect(() => {
    const url = status?.activationUrl;
    if (url) revealActivationUrl(url);
  }, [status?.activationUrl]);

  async function begin() {
    if (state === 'signing') return;
    armActivationPopup();`);

replaceOnce('apps/web/src/components/AmrLoginPill.tsx',
  `import { openExternalUrl } from '../providers/registry';`,
  `import { openExternalUrl } from '../providers/registry';
import { armActivationPopup, openActivationUrlFromClick, revealActivationUrl } from './openActivationUrl';`);
replaceOnce('apps/web/src/components/AmrLoginPill.tsx',
  `}: AmrAccountControlProps) {
  const { t } = useI18n();`,
  `}: AmrAccountControlProps) {
  const { t } = useI18n();
  useEffect(() => {
    if (activationUrl) revealActivationUrl(activationUrl);
  }, [activationUrl]);`);
replaceOnce('apps/web/src/components/AmrLoginPill.tsx',
  `            <a
              className="amr-login-activation__open"
              href={activationUrl}
              target="_blank"
              rel="noopener noreferrer"
            >`,
  `            <a
              className="amr-login-activation__open"
              href={activationUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(event) => {
                event.preventDefault();
                openActivationUrlFromClick(activationUrl);
              }}
            >`);
replaceOnce('apps/web/src/components/AmrLoginPill.tsx',
  `      if (loginPendingRef.current) return;
      loginPendingRef.current = true;`,
  `      if (loginPendingRef.current) return;
      armActivationPopup();
      loginPendingRef.current = true;`);

replaceOnce('apps/web/src/components/CloudSignInTip.tsx',
  `import { AmrActivationHintText } from './AmrActivationHintText';`,
  `import { AmrActivationHintText } from './AmrActivationHintText';
import { openActivationUrlFromClick } from './openActivationUrl';`);
replaceOnce('apps/web/src/components/CloudSignInTip.tsx',
  `                onClick={(event) => event.stopPropagation()}`,
  `                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  openActivationUrlFromClick(status.activationUrl!);
                }}`);

replaceOnce('apps/web/src/components/share/ShareSignInButton.tsx',
  `import { AmrActivationHintText } from '../AmrActivationHintText';`,
  `import { AmrActivationHintText } from '../AmrActivationHintText';
import { openActivationUrlFromClick } from '../openActivationUrl';`);
replaceOnce('apps/web/src/components/share/ShareSignInButton.tsx',
  `                <a
                  className="amr-login-activation__open"
                  href={status.activationUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                >`,
  `                <a
                  className="amr-login-activation__open"
                  href={status.activationUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(event) => {
                    event.preventDefault();
                    openActivationUrlFromClick(status.activationUrl!);
                  }}
                >`);

replaceOnce('apps/web/src/components/HomeInviteSurface.tsx',
  `import { useCloudSignIn } from './use-cloud-sign-in';`,
  `import { useCloudSignIn } from './use-cloud-sign-in';
import { openActivationUrlFromClick } from './openActivationUrl';`);
replaceOnce('apps/web/src/components/HomeInviteSurface.tsx',
  `{signedOut && signInState === 'signing' ? <div role="status">{signInStatus?.activationUrl ? <a href={signInStatus.activationUrl} target="_blank" rel="noopener noreferrer">{t('settings.amrActivationOpen')}</a> : null}`,
  `{signedOut && signInState === 'signing' ? <div role="status">{signInStatus?.activationUrl ? <a href={signInStatus.activationUrl} target="_blank" rel="noopener noreferrer" onClick={(event) => { event.preventDefault(); openActivationUrlFromClick(signInStatus.activationUrl!); }}>{t('settings.amrActivationOpen')}</a> : null}`);

replaceOnce('apps/web/src/components/InlineModelSwitcher.tsx',
  `} from 'react';`,
  `} from 'react';
import { armActivationPopup } from './openActivationUrl';`);
replaceOnce('apps/web/src/components/InlineModelSwitcher.tsx',
  `  const handleAmrSignIn = useCallback(async (
    attribution?: AmrEntryAttribution | null,
  ) => {
    const startedAt = Date.now();`,
  `  const handleAmrSignIn = useCallback(async (
    attribution?: AmrEntryAttribution | null,
  ) => {
    armActivationPopup();
    const startedAt = Date.now();`);

console.log('Applied Olares cloud login browser open');
