# Olares provider endpoint adaptation

Upstream: `nexu-io/open-design`, tag `open-design-v0.22.1`.

`apply-provider-hosts.mjs` runs before compilation. It adds the hostname from
the user-configured HTTP(S) model Base URL to a request-local allowlist. This
covers model discovery, connection checks, chat proxy requests and handoff
summaries. It neither persists hosts nor mutates the process environment, so
changing a provider URL leaves no stale global allowance behind.

The upstream URL syntax/protocol checks remain active. URLs supplied by upstream
responses, such as generated asset download links, retain their separate strict
SSRF validation and do not inherit this allowance.

`apply-local-delete.mjs` also sets Qwen thinking from `OD_THINKING_TOKEN_BUDGET`.
A positive integer enables thinking and caps it at that many tokens. Unset or 0
sends `enable_thinking: false`. The model server default stays unchanged.

`apply-login-open.mjs` opens the Cloud activation page from the sign-in click.
The container has no browser, and the Olares page blocks a plain new-window
link. The click arms a tab first; when the activation URL arrives it is loaded
there. If that tab is blocked, the page opens in the current view. The manual
link uses the same path, and copying it still works.

`apply-local-delete.mjs` lets the project delete dialogs work while signed out of
OpenDesign Cloud. Upstream treats a missing Cloud workspace context as a share
lookup error and disables Delete; on Olares that is the normal local mode, where
a project has no share publications to revoke. Signed-in behaviour is unchanged.

Patch contexts must match exactly once; a changed upstream implementation fails
the build instead of silently omitting the adaptation. Both target images run
`provider-hosts.test.mjs` against the compiled daemon module during construction.
This checks private provider endpoints, invalid protocols and isolation from
asset-download validation. Actual model quality and generation need separate
user testing.
