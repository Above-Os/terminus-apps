import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const root = process.argv[2] || '/app';
function replaceOnce(file, before, after) {
  const path = join(root, file);
  const source = readFileSync(path, 'utf8');
  if (source.split(before).length !== 2) throw new Error(`Upstream patch context changed: ${file}`);
  writeFileSync(path, source.replace(before, after));
}

const deleteFlow = 'apps/web/src/components/project-actions/useProjectDeleteFlow.ts';
// Olares: signed out of OpenDesign Cloud there is no workspace context, so the
// project is local-only and has no share publications to revoke.
replaceOnce(deleteFlow,
  `const shareReadStatus = target && !workspaceContext ? 'error' : status;`,
  `const localOnly = Boolean(target && !workspaceContext);
  const shareReadStatus = localOnly ? 'ready' : status;`);
replaceOnce(deleteFlow,
  `const activeShareCount = history ?`,
  `const activeShareCount = localOnly ? 0 : history ?`);

const workspace = 'apps/web/src/components/FileWorkspace.tsx';
replaceOnce(workspace,
  `const deleteShareStatus = deleteRequest && (!workspaceContext || deleteRequest.projectId`,
  `const deleteLocalOnly = Boolean(deleteRequest && !workspaceContext);
  const deleteShareStatus = deleteRequest && (deleteRequest.projectId`);
replaceOnce(workspace,
  `? 'error' : deleteHistoryStatus;`,
  `? 'error' : deleteLocalOnly ? 'ready' : deleteHistoryStatus;`);
replaceOnce(workspace,
  `const deleteActiveShareCount = deleteShareHistory`,
  `const deleteActiveShareCount = deleteLocalOnly ? 0 : deleteShareHistory`);
console.log('Applied Olares local project delete support');

const byok = 'apps/daemon/src/runtimes/byok-opencode.ts';
replaceOnce(byok,
  `if (!modelId) return null;`,
  `if (!modelId) return null;
  // Olares: OD_THINKING_TOKEN_BUDGET limits this app's Qwen thinking.
  // Unset or 0 turns thinking off. Other applications keep the server default.
  const thinkingBudget = Number(process.env.OD_THINKING_TOKEN_BUDGET);
  const thinkingOptions = Number.isInteger(thinkingBudget) && thinkingBudget > 0
    ? {
        chat_template_kwargs: { enable_thinking: true },
        thinking_token_budget: thinkingBudget,
      }
    : {
        chat_template_kwargs: { enable_thinking: false },
      };`);
replaceOnce(byok,
  `modalities: { input: ['text', 'image'], output: ['text'] },`,
  `modalities: { input: ['text', 'image'], output: ['text'] },
            options: thinkingOptions,`);
