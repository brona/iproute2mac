# Contributing Guidelines

Brief guidelines to provide a quickstart when contributing to iproute2mac. Generally contributions are welcome. The maintainer generally tries to respond within a week.

This project is inspired by iproute2 on Linux. More information on the `ip` command can be found in the [man-page](https://man7.org/linux/man-pages/man8/ip.8.html) and [iproute2-page](http://www.policyrouting.org/iproute2.doc.html). As advertised in the README, provided functionality is limited and it will never fully match iproute2. This is due to fundamentally different networking stacks between Linux and macOS, which is BSD derived. For the more complex functionality the abstractions vary dramatically and there is no point in trying to create a translation layer. E.g. see [d645515](https://github.com/brona/iproute2mac/commit/d64551516147d9be06eef49afc5c45ef601b8e7f) for how we re-aligned the `ip route flush cache`.

The `ip` and `bridge` commands have source here:
* https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/ip/ip.c#n86
* https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/bridge/bridge.c#n52

## Objectives of the project

The primary goal is to help humans who are used to `ip` command with basic networking troubleshooting on macOS, especially when using VPNs, multiple NICs and other every day setups.

The secondary goal is to provide a compatibility layer for scripting - to allow scripts utilising `ip` command on Linux-based systems to run on macOS. We should not diverge from iproute2 behaviour. This means we should aim to match exit codes, output formatting and STDERR/STDOUT behaviour. This can be helpful for build systems and other dev tools, however generally we shouldn't aim at embedding iproute2mac into any production grade system as at this point we can't guarantee correctness or general reliability.

The last goal is to optionally provide quality of life enhancements and convenience features to the existing `ip` commands which are meaningful to iproute2mac users. For example we have `ip link set en0 address random` and `ip link set en0 address factory`, which do not have equivalents in iproute2.

**When porting features from iproute2 to iproute2mac, the general principle should be predictable and fail-safe behaviour.** Exiting with "Not implemented", is preferred over dummy or made-up information being provided, or quietly dropping unimplemented options or commands. We shouldn't confuse our clients or create any inconsistencies. Practically, if the underlying Linux/macOS stacks differ too much, the script should terminate with error code rather than pretend it works or implement some hacky band aid type solution.

## Developer Setup
To test your code it can be useful to create an alias with the following command in your terminal:
```bash
alias ip="<path-to-repo>/iproute2mac/src/ip.py"
alias bridge="<path-to-repo>/iproute2mac/src/bridge.py"
```
To have it permanently add the above command to your `~/.zshrc` or `~/.bashrc` file.

## Testing

Unfortunately we do not have unit tests or any integration tests with reasonable coverage. This makes contributions quite risky. We effectively parse output of other binaries like `ifconfig` and thus the overall approach is quite fragile. Not even mentioning that there might be changes of behaviour between macOS versions.

1. Manual testing on your machine is the first step, we have [test/commands.sh](./test/commands.sh) script, which has couple standard use-cases and tests for exit codes. However you need to check correctness yourself.
    * This script should pass for every pull request and release.
    * If you add new commands please extend the test file.
2. [BrewTestBot](https://docs.brew.sh/BrewTestBot) runs the tests on multiple platforms (See example [here](https://github.com/Homebrew/homebrew-core/pull/179084)) during update of our Homebrew formula.
    *  During every release, it runs commands defined [here](https://github.com/Homebrew/homebrew-core/blob/master/Formula/i/iproute2mac.rb#L25) and checks for non-error exit codes.

**Any contributions refactoring the code and adding more comprehensive tests would be very welcome**. Generally we should aim to capture several sample real outputs of `ifconfig` and `netstat` on macOS and store the expected Linux-like output. Then we would feed the sample output into iproute2mac to mock the real CLI execution and compare the outputs. For commands that modify the stack, we should store the expected CLI command that is begin executed.

## Homebrew formula

https://github.com/Homebrew/homebrew-core/blob/master/Formula/i/iproute2mac.rb

## Release

1) [Create a new release](https://github.com/brona/iproute2mac/releases/new) on Github with assigning a new version tag, e.g. `v1.5.0`.
2) Download and re-upload the source and add it as an asset to the release, e.g. `
iproute2mac-1.5.0.tar.gz`. This allows for download statistics to be captured on Github.
3) Calculate sha256 of the release, e.g. `sha256sum iproute2mac-1.5.0.tar.gz`
4) [Request Github access token](https://github.com/settings/tokens), requesting `public_repo` and `workflow` scopes.
5) [Bump the Homebrew formula](https://docs.brew.sh/How-To-Open-a-Homebrew-Pull-Request#submit-a-new-version-of-an-existing-formula), e.g. Run `HOMEBREW_GITHUB_API_TOKEN=<token> brew bump-formula-pr --url="https://github.com/brona/iproute2mac/releases/download/v1.5.0/iproute2mac-1.5.0.tar.gz" --sha256 "f842776ada1a51bb4a5c34e1e68471c85d7bf9f43511bdfef008074f82876a49" iproute2mac`

If you are doing bigger changes to the Homebrew formula, you need to fork and branch [homebrew-core](https://github.com/Homebrew/homebrew-core) manually.

## Commit and Pull Request hygiene

1) Small pull requests with a single feature are preferred.

2) Your Pull Request should include necessary changes to [test/commands.sh](./test/commands.sh) and [./README.md](./README.md).

3) Please add reasonable commit messages.

4) Please maintain commit atomicity, iproute2mac should work at each commit. E.g. You can squash your last 3 commits using: `git reset --soft HEAD~3`; `git commit`; `git push -f`

5) As part of your first pull request, please add yourself to [AUTHORS](./AUTHORS).
