# Make the container fixture drivable outside pytest

> **Status: proposal only, and externally blocked.** Recorded so the
> investigation behind it is not lost. `specs/`, `design.md` and `tasks.md` are
> not yet written, so this change does not validate. Depends on
> `replace-slurm-container-with-ssh`, and on a change in a *different*
> repository — see "External blocker".

## Why

The integration container can currently only be started by running the test
suite. Every iteration on the fixture therefore costs a full pytest cycle, and
any inspection of the running container has to be smuggled in through
assertions. The `test_ssh_transport_raw` test is the visible symptom: sixty-five
lines that walk through `echo`, `sinfo`, an SFTP upload, a job submission and a
log dump, which is a manual debugging session frozen into a test because there
was no other way to perform one.

A small command-line entry point that brings the container up, prints its
connection details, holds it, and tears it down would remove that cost, and
would give the documentation something concrete and runnable to point at. If the
pytest fixture is a thin wrapper over the same entry point, the documented
procedure and the tested procedure cannot diverge.

## What Changes

- Add a command-line entry point over the container helper supporting bring-up,
  reporting connection details, and teardown.
- Reduce the pytest fixture to a wrapper over it.
- Reconsider `test_ssh_transport_raw` once the fixture reports its own readiness
  stages, since most of what it checks becomes the fixture's responsibility.

## Capabilities

### Modified Capabilities

- `testing-and-ci`: likely a requirement that the integration container can be
  started and inspected independently of a test run, so that the documented and
  tested procedures share one implementation. To be confirmed when the fixture's
  shape is settled.

## External blocker

This cannot be exercised in a sandboxed development container, and the reason is
not fixable from this repository:

- A nested rootless container engine in such a sandbox can only map a single
  user ID, because `newuidmap` fails there.
- Creating a user namespace with a single mapping forces the kernel to set
  `setgroups` to `deny` for that namespace.
- OpenSSH privilege separation calls `setgroups` before authentication, so no
  SSH login can complete. Verified directly: the daemon starts and listens, and
  the connection is reset at authentication with
  `setgroups: Operation not permitted [preauth]`.

This applies to any SSH-based container, with or without a scheduler, so
simplifying the image does not help. The fix belongs to the sandbox
configuration: supply a subordinate ID range that exists inside the sandbox, and
grant the capability needed to install a multi-ID mapping. That should be an
opt-in launch mode rather than a default, because it lets sandboxed processes
create nested containers, which widens the blast radius even though it confers
no privilege on the host.

**Before designing that**, resolve an unexplained observation: `newuidmap` is
installed set-user-ID root, `NoNewPrivs` is unset, the relevant capability is in
the bounding set, and the filesystem is not mounted `nosuid`, yet mapping even a
single ID returns `EPERM`. If the cause is something other than the mismatched
subordinate ID range, granting the capability alone may not be sufficient.

## Non-goals

- **Changing the sandbox configuration from this repository.**
- **Making the container tests run in every development environment.** Where a
  container engine is unavailable they skip, and the interpreter-level coverage
  runs instead.

## Impact

- The container helper module and the fixtures that use it, plus a console entry
  point.
- Potentially removes or substantially shrinks one existing test.
