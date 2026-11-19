# Upgrade to Chart 1.0.26

If `/app/server/.env` already points to the non-empty `/app/server/storage/.env`, upgrade normally. The application verifies a local database and storage backup before migrations.

For a legacy installation storing configuration only inside its container, perform the following export **before** starting the upgrade or stopping the old instance. Run the command in a terminal for the running `anythingllm` container, as its application user. Keep the terminal open until the export reports success. It preserves the original bytes and links the active environment file to persistent storage so subsequent settings saves survive the upgrade. Keep the backup with the corresponding database.

```sh
node - <<'JS'
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const source='/app/server/.env',destination='/app/server/storage/.env';
if(!fs.existsSync(source)||!fs.statSync(source).isFile())throw new Error('Legacy configuration is missing; refusing upgrade');
const bytes=fs.readFileSync(source);
if(bytes.length===0)throw new Error('Legacy configuration is empty; refusing upgrade');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const directory='/app/server/storage/.olares-upgrade/config-migration';
fs.mkdirSync(directory,{recursive:true,mode:0o700});
const digest=hash(bytes),archive=path.join(directory,digest+'.env');
if(!fs.existsSync(archive))fs.writeFileSync(archive,bytes,{flag:'wx',mode:0o600});
if(hash(fs.readFileSync(archive))!==digest)throw new Error('Configuration backup verification failed');
if(fs.realpathSync(source)!==destination){
  if(fs.existsSync(destination)){
    const previous=fs.readFileSync(destination),prior=path.join(directory,hash(previous)+'.env');
    if(!fs.existsSync(prior))fs.writeFileSync(prior,previous,{flag:'wx',mode:0o600});
    if(hash(fs.readFileSync(prior))!==hash(previous))throw new Error('Previous persistent configuration backup verification failed');
  }
  const pending=destination+'.migration-pending';
  const fd=fs.openSync(pending,'w',0o600);try{fs.writeFileSync(fd,bytes);fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  if(hash(fs.readFileSync(pending))!==digest)throw new Error('Exported configuration differs');
  fs.renameSync(pending,destination);
  // Keep subsequent settings saves persistent during the handover.
  const link=source+'.migration-link';
  try{fs.unlinkSync(link);}catch(e){if(e.code!=='ENOENT')throw e;}
  fs.symlinkSync(destination,link);fs.renameSync(link,source);
}
fs.chmodSync(destination,0o600);
if(hash(fs.readFileSync(source))!==hash(fs.readFileSync(destination)))throw new Error('Persistent configuration verification failed');
fs.writeFileSync(path.join(directory,'verified.json'),JSON.stringify({sha256:digest,bytes:bytes.length}),{mode:0o600});
console.log('Legacy configuration exported and verified; values were not logged.');
JS
```

If the old container is already gone, recover the original configuration from a backup. When the database exists without a non-empty persistent configuration, startup halts before database migration. The Chart does not create a replacement in this case.

## Historical notes for Chart 1.0.24

The automated hook described below was removed in 1.0.26 because injected network sidecars prevented the hook Job from finishing. The previous migration test records are kept for reference.


Chart 1.0.23 required a manual export of `/app/server/.env` before upgrading a legacy installation. Legacy Charts kept that file in the container layer. Without the export, replacing the old Pod made the original provider settings unavailable and the new initialization correctly refused to migrate the existing database. Release notes alone did not make the upgrade automatic.

## Running legacy installations

The namespace-scoped Helm pre-upgrade hook now runs before replacing the Deployment. It locates exactly one running application Pod and executes the export inside that container, as its existing application user. No configuration values leave the container or appear in logs.

The hook archives the original bytes under `storage/.olares-upgrade/config-migration/<sha256>.env`, verifies the archive, atomically writes `storage/.env` with mode 0600, and atomically changes the old server configuration path into a symlink. Settings saved during the remaining handover therefore also reach persistent storage. Any previous, different persistent configuration is archived before replacement. Repeated execution preserves the archives and verifies their hashes.

The existing init-container SQLite/storage backup still runs before upstream migrations. Missing/empty source configuration, corrupt existing archives, ambiguous Pod selection, denied access or a hook failure stops the Helm upgrade before it replaces the old Deployment. Hook credentials have only namespace-local Deployment-read, Pod-read/list and Pod-exec permissions; successful hook resources are removed.

## Already interrupted upgrades and stopped legacy installations

This fix cannot reconstruct configuration that existed only in an already-deleted container. Restore the **original** environment file from an operator backup or a recoverable old container before resuming such an installation. Keep the database, files and signing/encryption material together. Do not create an empty `.env`, copy another instance's environment, reset the database, or assume a new image's default configuration preserves the previous provider credentials.

The current test machine's original `anythingllm` instance hit this condition while testing Chart 1.0.23. Its operation was cancelled and it remains stopped with its data and verified pre-upgrade SQLite backup retained. It has not been represented as recovered. The successful regressions below use separately identified, complete old-version instances.

An installation already using the persistent configuration layout can also be updated while stopped; its normal init-container checks remain authoritative. If a legacy application was stopped before its configuration was exported, recover that original configuration rather than silently restarting with defaults.

## Regression record — 2026-10-23

Target: AnythingLLM 1.18.0, public Chart 1.0.24. Olares test host: Linux amd64, Olares 1.12.7. Isolated Upload aliases retain the same identity and persistent storage throughout each path. Alias-only names, workload/Secret references and test package versions differ from the public package. No tests here modify or overwrite the original formal instance's data.

| Path | Checks |
| --- | --- |
| Actual market 1.14.1 / Chart 1.0.17 → 1.18.0 | Started without `storage/.env`; automatic hook exported configuration; same administrator ID, API key, workspace ID/slug and attachment hash; original non-default provider/address/model/token-limit and synthetic secret hash; byte-identical `.env`; SQLite integrity; stop/resume persistence |
| Official 1.17.0 image with the previously selected v3 test wrapper / Chart 1.0.22 → 1.18.0 | Same configuration, account, workspace, attachment, database and stop/resume checks; not claimed to be an unchanged historical market Chart |
| Fresh 1.18.0 installation | Account initialization/login, workspace creation, attachment save, non-default configuration save, stop, update while stopped, resume and data/configuration readback |

The first 1.14.1 candidate failed safely before replacing the old Pod because of a Job mesh-injection compatibility issue. The corrected hook disables shared-caller outbound injection for its one-shot Job and limits `runAsNonRoot` to the helper container. Corrected 1.14.1 used alias Chart 1.0.25; corrected 1.17.0 used alias 1.0.24. Fresh 1.0.24 was installed, then its final guard-diagnostic update was exercised as alias 1.0.25 while stopped. Public Chart numbering remains one patch above remote 1.0.23.

Both migrated SQLite archives were reopened and their original administrator/workspace rows checked. Storage archives were fully read and compared with recorded checksums. Configuration files remained mode 0600; runtime UID was 1000. Application and proxy logs after the corrected upgrades contained no error/warning matches and all containers were ready with zero restarts before the deliberate stop/resume tests. A Market restart request timed out after completing its stop phase; explicit resume and full readback passed, and this transport interruption is retained in the local evidence.

Six script safety cases passed in separate temporary directories: missing persistent configuration, preserving an existing different destination, repeated execution plus a later settings save, missing source refusal, empty source refusal, and corrupt archive refusal.

The hook helper `beclab/bitnami-kubectl:1.0.0` has verified amd64/arm64 manifests. Only amd64 was exercised. These regressions target configuration migration; the synthetic provider endpoint is loopback and no external LLM inference, paid provider, OAuth or SMTP integration was exercised. The attachment is a stored test file; this report does not claim new document indexing or vector retrieval coverage.

Local evidence is retained separately with configuration values and credentials excluded from this contribution. The original formal instance remains stopped pending recovery of its original configuration. Other application upgrades were paused at the requester's instruction.
