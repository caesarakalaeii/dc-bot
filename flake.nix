{
  # Keep this line accurate and one line long: `nix flake metadata` prints it,
  # and it is the first thing a cold agent learns about the repo.
  description = "dc-bot -- OpenAI-backed Discord DM bot (discord.py, Pillow receipt faking). Run `nix flake show` for the command map.";

  # nixpkgs is the only input, on purpose. The only thing this flake would use
  # flake-utils for is eachDefaultSystem, and the canonical machinery below
  # already defines `systems` and `forAllSystems` itself -- so adding it would
  # buy a second lock node and a second upstream and nothing else.
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    # `self` is mandatory: the anchor in the canonical machinery is built from
    # it, and a flake whose outputs pattern omits it does not evaluate. `...`
    # rather than a closed { self, nixpkgs } so that adding a second input later
    # does not also require widening this line.
    { self, nixpkgs, ... }:
    let
      lib = nixpkgs.lib;

      # ======================================================================
      # PER-REPO SECTION -- everything below the sentinel is fleet-canonical
      # ======================================================================
      # The canonical block reads exactly these names out of this section:
      # repoName, toolchain, nativeLibs, envVars, commands, extraChecks (plus
      # nixpkgs, self and lib). Anything else declared here is invisible to it.
      #
      # `systems` and `forAllSystems` are NOT ours to define -- they live in the
      # block, and re-declaring them here is a duplicate-attribute error at
      # eval. Likewise the anchor: this repo used to carry its own pair of
      # `repoMarker = "bot_start.py"` and `git rev-parse --show-toplevel`, which
      # adopts any enclosing git checkout that happens to contain a file of that
      # name. The canonical anchor compares the whole flake.nix and supersedes
      # it.

      # ======================================================================
      # PER-REPO BLOCK 1 -- the dev-shell banner name
      # ======================================================================
      # The clone/directory name. Cosmetic -- it is only how a human tells two
      # open dev shells apart -- but it still has to be right.
      repoName = "dc-bot";

      # ======================================================================
      # PER-REPO BLOCK 2 -- the toolchain
      # ======================================================================
      # Everything the commands need on PATH. `checks.toolchain` realises this
      # closure, so a typo'd attr name fails at the flake gate instead of
      # surfacing as "command not found" halfway through a task.
      #
      # Explicit `pkgs.foo`, never `with pkgs; [ ... ]`: when an attr disappears
      # in a nixpkgs bump, `with` reports a bare undefined identifier with no
      # hint of which set it came from, and the name is not greppable.
      #
      # python313 rather than python3, because the Dockerfile this repo actually
      # deploys from says `FROM python:3.13-slim` -- the dev shell matches the
      # image. It is not invoked directly by any verb; UV_PYTHON below is what
      # points uv at it.
      toolchain = pkgs: [
        # ---- named by the verbs below ----
        pkgs.python313
        pkgs.uv
        pkgs.ruff

        # ---- named by no verb below; on PATH for the human at the prompt ----
        pkgs.git
        pkgs.jq
        pkgs.gnumake
      ];

      # ======================================================================
      # PER-REPO BLOCK 3 -- libraries that get dlopened, not linked
      # ======================================================================
      # manylinux wheels carry .so files that are dlopened at runtime, so
      # neither patchelf nor the nix linker ever rewrites them, and NixOS has no
      # /usr/lib for them to fall back on. LD_LIBRARY_PATH is the only lever
      # left, and the canonical ldPreamble prepends rather than assigns it.
      #
      # Measured against this requirements.txt, installed from PyPI into a uv
      # venv on pkgs.python313, with LD_LIBRARY_PATH unset: `ldd` reports
      # `libz.so.1 => not found` for 10 of the installed wheel .so files and
      # `libstdc++.so.6 => not found` for 3 (_frozenlist, _avif, libavif).
      #
      #   * stdenv.cc.cc.lib is load-bearing. Without it
      #     `from frozenlist import _frozenlist` raises "libstdc++.so.6: cannot
      #     open shared object file", and frozenlist -- pulled in by aiohttp --
      #     falls back to its pure-Python implementation without saying so.
      #   * zlib is currently redundant: Pillow decodes paypal_blank.png fine
      #     with LD_LIBRARY_PATH unset, because the interpreter has already
      #     mapped libz.so.1 through its own zlib extension module and the
      #     loader reuses a soname that is already in the process. It stays as
      #     belt-and-braces -- requirements.txt pins no versions, so the wheel
      #     set can change under this flake without warning -- and one extra
      #     store path on a prepended variable costs nothing.
      nativeLibs = pkgs: [
        pkgs.stdenv.cc.cc.lib
        pkgs.zlib
      ];

      # ======================================================================
      # PER-REPO BLOCK 4 -- constant environment variables
      # ======================================================================
      # Constants only. Anything that must READ an existing value
      # (LD_LIBRARY_PATH) or UNSET something (SOURCE_DATE_EPOCH) is handled by
      # the canonical block. This attrset is applied to BOTH surfaces -- the dev
      # shell and every wrapper -- so a verb cannot behave differently depending
      # on how it was invoked.
      #
      # Deliberately absent: DISCORD_TOKEN, OPENAI_API_KEY, CHANNEL_ID, GUILD_ID,
      # STREAMER_NAME, ADMIN_PASSWORD. bot_start.py defaults each of those six to
      # an Exception object and raises it during config assembly, so they are
      # required at startup -- and they are secrets, so they belong in the
      # caller's environment, never in a world-readable /nix/store path.
      envVars = pkgs: {
        # Keep uv on the nix interpreter rather than one it fetched itself: with
        # UV_PYTHON set, `uv venv` reports "Using CPython 3.13.15 interpreter at:
        # /nix/store/...-python3-3.13.15/bin/python". UV_PYTHON_DOWNLOADS=never
        # is the environment spelling of uv's own --no-python-downloads flag.
        UV_PYTHON = "${pkgs.python313}/bin/python";
        UV_PYTHON_DOWNLOADS = "never";
        # Matches the Dockerfile's `ENV PYTHONUNBUFFERED=1`. This bot logs its
        # way through a conversation, and a buffered stdout hides the log lines
        # an agent is waiting on until the process exits.
        PYTHONUNBUFFERED = "1";
      };

      # ======================================================================
      # PER-REPO BLOCK 5 -- the command map
      # ======================================================================
      # THE single source of truth. It generates `apps` (so `nix run .#test`
      # works), the `dev-*` wrappers on PATH inside the shell, and `dev-help`.
      # Nothing is written twice, so `nix flake show` can never disagree with
      # what `dev-test` actually runs.
      #
      # `build` is deliberately absent rather than stubbed: this repo produces no
      # local artifact. The deployable is a container image, and
      # .github/workflows/build_and_push.yml builds it with `docker build .`
      # against a daemon nix cannot supply.
      #
      # `text` is bash under `set -euo pipefail`, shellcheck'd at BUILD time, and
      # runs with $SRC_ROOT, $REPO_ROOT and need_writable_checkout already in
      # scope -- see the canonical block below for what each of those means.
      #
      # THE ANCHORING INVARIANT, and it is not negotiable: a verb behaves the
      # same no matter which directory it was invoked from, and never reads or
      # writes a file outside this repo. So no verb here leans on a bare
      # trailing "$@" -- both ruff and pytest read "no paths given" as "do it to
      # the current directory", and that directory belongs to the caller, not to
      # us. Anchor with
      # whatever form the tool actually accepts: `cd "$REPO_ROOT"` plus an
      # explicit `.` for ruff, an explicit target argument for pytest. Explicit
      # user arguments still win, so `nix run .#fmt -- bot.py` keeps working --
      # paths are then resolved from the repo root, which is also where an agent
      # almost always already is.
      commands = pkgs: {
        setup = {
          # pytest is installed alongside requirements.txt on purpose: the repo
          # ships five pytest files (test_utils, test_identity,
          # test_bot_identity, test_bot_completion, test_welcome_cancel) but
          # requirements.txt lists runtime deps only (discord.py, openai,
          # requests, pillow, aiohttp) and there is no requirements-dev.txt to
          # add pytest to without touching the repo's dependency contract.
          #
          # --allow-existing, because without it a second run dies before
          # `uv pip install` is ever reached. Measured with uv 0.12.3: over an
          # existing venv, `uv venv .venv` prints "error: Failed to create
          # virtual environment / Caused by: A virtual environment already
          # exists at: .venv" and exits 2, which under `set -e` aborts the verb
          # -- so the bootstrap failed on exactly the trees that had already been
          # bootstrapped once, i.e. every re-run after a requirements.txt change
          # and every agent retry loop. With the flag the same call exits 0 and
          # the install re-resolves, so this verb is idempotent.
          description = "(network) create/update .venv from requirements.txt, plus pytest for the test suite";
          text = ''
            need_writable_checkout
            uv venv --allow-existing "$REPO_ROOT/.venv"
            uv pip install --python "$REPO_ROOT/.venv/bin/python" -r "$REPO_ROOT/requirements.txt" pytest
          '';
        };
        test = {
          # The venv interpreter by absolute path. pytest is deliberately not in
          # the toolchain, so there is no store copy on PATH to shadow it, and
          # only this interpreter can import discord.py, openai and Pillow.
          #
          # "$REPO_ROOT" "$@" and not "''${@:-$REPO_ROOT}": extra pytest flags
          # (`-- -q -k welcome`) have to compose with the target rather than
          # replace it, or a flags-only invocation would collect from the
          # caller's cwd again.
          #
          # Guarded because the run writes: on a clean export the only files a
          # full run added to the tree were .pytest_cache/ and __pycache__/,
          # both already gitignored -- the tests reach persistence/ only after
          # monkeypatch.chdir into a tmp_path, so no conversation JSON lands in
          # the checkout.
          description = "run the pytest suite (needs `setup` first)";
          text = ''
            need_writable_checkout
            "$REPO_ROOT/.venv/bin/python" -m pytest "$REPO_ROOT" "$@"
          '';
        };
        lint = {
          # The repo ships no pyproject.toml and no ruff.toml, so this is ruff's
          # default rule set. On this checkout it reports 61 findings across 12
          # rules -- led by 17 UP032 (f-string), 9 I001 (unsorted-imports) and 8
          # BLE001 (blind-except) -- and therefore exits 1 on an untouched tree.
          # That is the honest state of the code, not a broken flake; do not
          # "fix" it by weakening the command.
          #
          # `cd` + an explicit `.` rather than a bare "$@": ruff with no path
          # argument inspects the process's cwd, so a bare "$@" here would grade
          # the CALLER's files whenever this is invoked by flake URL from
          # somewhere else -- and where the caller has no Python at all, ruff
          # prints "warning: No Python files found under the given path(s)",
          # then "All checks passed!", and exits 0. A green gate that read
          # nothing. The cd also covers the flags-only case (`-- --statistics`),
          # which "''${@:-$REPO_ROOT}" would not.
          #
          # --no-cache when the anchor is not writable: ruff writes .ruff_cache
          # into the directory it was pointed at, and on an unwritable one it
          # aborts with "error: Failed to initialize cache at .../.ruff_cache:
          # Permission denied" and exit 2 -- a gate that dies before reading
          # anything, which is the same lie wearing a different exit code.
          # Nothing is lost: a store snapshot's path changes with its content,
          # so a cache there could never be reused.
          description = "ruff check the whole repo (exits 1 on the pre-existing findings)";
          text = ''
            cd "$REPO_ROOT"
            cache=()
            [ -w "$REPO_ROOT" ] || cache=(--no-cache)
            ruff check "''${cache[@]}" "''${@:-.}"
          '';
        };
        fmt = {
          # Formats the whole tree: `ruff format --check` currently calls 11 of
          # this repo's 19 Python files unformatted, so a bare run rewrites 11
          # files. Pass explicit paths (`nix run .#fmt -- bot.py`, resolved from
          # the repo root) to keep a diff reviewable, or `-- --check` to see
          # what it would touch.
          #
          # Anchored exactly like lint, and this is the half where getting it
          # wrong does damage rather than just lying: ruff format MUTATES, so a
          # bare "$@" here would rewrite whatever Python happens to be sitting
          # in the caller's directory.
          #
          # need_writable_checkout rather than a hand-rolled `[ -w ]` test: the
          # question a mutating verb has to answer is "did the anchor find a
          # real checkout of this repo", and the canonical guard answers exactly
          # that and prints a refusal naming the verb and the directory.
          description = "ruff format the whole repo (rewrites files)";
          text = ''
            need_writable_checkout
            cd "$REPO_ROOT"
            ruff format "''${@:-.}"
          '';
        };
        run = {
          # lint and fmt cd for anchoring; this one cd's because the CODE needs
          # it. Every persistence path is cwd-relative -- utils.py, logger.py
          # and bot.py all build "persistence", "persistence/logs" and
          # "persistence/media/..." as bare relative paths, exactly as in the
          # container where WORKDIR is /app. Without the cd, starting the bot
          # from a subdirectory would silently fork a second set of conversation
          # files. Guarded for the same reason: bot.py creates those directories
          # on startup, so this verb writes.
          #
          # run.sh is bypassed deliberately -- it base64-decodes WHITE_LIST and
          # BLACK_LIST into /app/persistence/whitelist_${BOT_NAME}.json and
          # /app/persistence/blacklist_${BOT_NAME}.json, absolute paths that do
          # not exist outside the image. Write
          # persistence/whitelist_<BOT_NAME>.json by hand locally.
          description = "(network) start the bot -- needs DISCORD_TOKEN, OPENAI_API_KEY, CHANNEL_ID, GUILD_ID, STREAMER_NAME, ADMIN_PASSWORD";
          text = ''
            need_writable_checkout
            cd "$REPO_ROOT"
            exec "$REPO_ROOT/.venv/bin/python" bot_start.py "$@"
          '';
        };
      };

      # ======================================================================
      # PER-REPO BLOCK 6 -- checks beyond the canonical two
      # ======================================================================
      # `checks.anchoring` in the block below proves the MECHANISM behaves. This
      # one proves THIS repo's verbs actually use it: dev-lint must read this
      # repo and not the tree it was launched from, and dev-fmt must refuse
      # rather than rewrite that tree.
      #
      # The pytest suite is deliberately NOT a check: it needs the .venv that
      # `setup` populates over the network, and a nix build has no network.
      extraChecks = pkgs: {
        verbAnchoring =
          pkgs.runCommand "verb-anchoring-check"
            {
              nativeBuildInputs = lib.attrValues (wrappers pkgs);
            }
            ''
              set -euo pipefail

              # A decoy carrying the markers a naive anchor would accept for a
              # Python repo -- a root bot.py, a requirements.txt, a flake.nix --
              # plus one filename this repo does NOT contain.
              mkdir decoy
              cd decoy
              printf 'import os\nx  =1\n' > bot.py
              printf 'import json\ny  =2\n' > sibling_only.py
              printf 'requests\n' > requirements.txt
              printf '{ description = "x"; outputs = _: { }; }\n' > flake.nix
              cp -r . ../decoy.orig

              # `--show-files` makes "which files did you read?" answerable
              # without depending on the repo still having findings: asserting a
              # finding count would turn somebody fixing the code into a broken
              # check. Grep by NAME, not by directory -- dev-lint cd's to its
              # anchor, so if it wrongly landed on the decoy the paths it prints
              # would be the decoy's own and a grep for "decoy" would match
              # nothing.
              dev-lint --show-files > lint.log 2>&1 || true
              if grep -q sibling_only lint.log; then
                echo "dev-lint read the decoy" >&2
                cat lint.log >&2
                exit 1
              fi
              # ...and it must have read SOMETHING: a verb that read nothing at
              # all also passes the test above.
              if ! grep -qF -- ${lib.escapeShellArg "${self}"} lint.log; then
                echo "dev-lint read neither the decoy nor this repo" >&2
                cat lint.log >&2
                exit 1
              fi

              # Refusal, not silence.
              if dev-fmt > fmt.log 2>&1; then
                echo "dev-fmt succeeded in a foreign tree; it must refuse" >&2
                cat fmt.log >&2
                exit 1
              fi

              # `*.log`, and every log file must match it -- a file named
              # plainly `log` is not excluded by --exclude='*.log' and would
              # fail this diff.
              diff -r --exclude='*.log' . ../decoy.orig
              touch "$out"
            '';
      };

      # >>>>> BEGIN CANONICAL MACHINERY v1 <<<<<
      # ======================================================================
      # Everything from the BEGIN sentinel above to the END sentinel on the last
      # line of this file is fleet-canonical text: the same bytes in every repo
      # that carries this flake style. That is a checkable claim, not a boast --
      #
      #   sed -n '/BEGIN CANONICAL MACHINERY v1/,$p' flake.nix | sha256sum
      #
      # prints the same digest in every repo, or one of them has been edited.
      # (`,$p`, not a range ending on the END sentinel: a range whose closing
      # pattern were spelled out here would terminate on this very comment.)
      # Nothing here names a repository, a language, a tool or a project file.
      # If you find such a name below, it is contamination: the fix is to move
      # it into the per-repo section above, never to special-case it here.
      #
      # This region READS exactly these names from the per-repo section:
      #   nixpkgs  self  lib  repoName  toolchain  nativeLibs  envVars
      #   commands  extraChecks
      # and DEFINES exactly these:
      #   systems  forAllSystems  ldPreamble  rootPreamble  guardPreamble
      #   wrappers  helpFor  anchorCheck
      # plus the four flake outputs apps / devShells / checks / formatter.
      # Anything else in scope is invisible to it. The types of those eight
      # inputs, and the shell variables this region exports into command texts,
      # are specified in INTERFACE.md, which travels with this block.
      #
      # To change behaviour here you change it in every repo at once and bump
      # the version in both sentinels. A local edit is a bug by construction:
      # the digest above stops matching, and -- because rootPreamble anchors on
      # flake.nix byte-identity -- an edited working tree also stops being
      # recognised by wrappers built from the previous revision.
      # ======================================================================

      # ---- systems policy: decided once for the whole fleet ----
      #
      # Read this list as "evaluated on three, built on one". That is what was
      # measured, and it is all it means:
      #   * `nix flake check --all-systems` passes, so every output attribute
      #     below EVALUATES on all three systems.
      #   * only x86_64-linux has ever been BUILT. The machine this was verified
      #     on has no aarch64 emulation -- no binfmt handler, and `extra-
      #     platforms` is x86-only -- so aarch64 cannot be built there at all.
      # It is not a statement that anything works on aarch64. Do not upgrade it
      # into one in a README.
      #
      # Evaluating all three is still worth its seconds, because the failure it
      # catches is an eval-time failure: a `pkgs.<attr>` that exists on Linux
      # and not on darwin (`stdenv.cc.cc.lib` is the usual one) throws during
      # evaluation, and `nix flake check` without --all-systems checks only the
      # current system and sails straight past it.
      #
      # x86_64-darwin is deliberately absent. nixpkgs 26.11 replaced that whole
      # attribute set with a `throw`. genAttrs is lazy, so plain `nix develop`
      # on Linux would not notice -- it detonates later, on the --all-systems
      # run this policy requires. Add it back only against a separate
      # nixpkgs-26.05-darwin input.
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];

      # Stand-in for flake-utils.lib.eachDefaultSystem. Passes `pkgs` rather
      # than a system string, because that is what every call site wants, and
      # keeps the system list in this file rather than in a second input's
      # hardcoded copy of it.
      forAllSystems = f: lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      # Prepend, never assign: a host LD_LIBRARY_PATH may be carrying something
      # the user needs, and clobbering it breaks binaries they launch from here.
      # Linux only -- on darwin the loader variable is DYLD_*, and exporting a
      # Linux-shaped value there is at best useless.
      #
      # `&&` short-circuits in Nix, so on darwin `nativeLibs pkgs` is never
      # forced. That is load-bearing for the systems policy above: it is what
      # lets a repo list Linux-only attrs in nativeLibs and still evaluate on
      # aarch64-darwin. Do not reorder the two operands.
      ldPreamble =
        pkgs:
        lib.optionalString (pkgs.stdenv.hostPlatform.isLinux && nativeLibs pkgs != [ ]) ''
          export LD_LIBRARY_PATH="${lib.makeLibraryPath (nativeLibs pkgs)}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        '';

      # Every command gets $SRC_ROOT and $REPO_ROOT. `nix run` and `nix develop`
      # both start in whatever directory they were invoked from, and no verb may
      # act on that directory -- these two are what it acts on instead.
      #
      # $SRC_ROOT is this flake's own source, snapshotted into the store when
      # the flake was evaluated. It is the one anchor that is always available:
      # `nix run /path/to/repo#lint` tells the running program nothing whatever
      # about /path/to/repo (flake refs are location-independent by design, and
      # there is no $FLAKE_DIR to read), so without `self` a wrapper invoked
      # that way has literally no way to name the repo it belongs to. Two
      # limitations worth knowing: it is read-only, being a store path, and in a
      # git checkout it contains only TRACKED files.
      #
      # $REPO_ROOT is the writable checkout when the caller is standing in one,
      # and $SRC_ROOT when they are not. Three things this deliberately is NOT:
      #
      #   * NOT `pwd`. A fallback to the caller's directory is how `fmt`
      #     rewrites a stranger's source tree and how `lint` prints "all checks
      #     passed" having read none of this repo.
      #   * NOT `git rev-parse --show-toplevel`. Run from inside some OTHER git
      #     repo it cheerfully answers with THAT repo's top level. It also needs
      #     git on PATH and a .git directory, so it fails on an export and in
      #     any wrapper whose toolchain omits git.
      #   * NOT an inherited $REPO_ROOT from the environment. The dev shell
      #     EXPORTS this variable, so honouring it would mean that running
      #     `nix run /path/to/B#fmt` from inside repo A's dev shell points B's
      #     formatter at A. An explicit path argument is how a caller overrides
      #     a verb's target; an ambient variable is how they do it by accident.
      #
      # Instead: walk up from $PWD and take the first ancestor that IS this
      # repo, proved by carrying a byte-identical flake.nix. A single tracked
      # filename, a marker directory, or a set of them is not proof -- sibling
      # repos in a fleet share those, and a decoy can be built to carry any list
      # of names you care to publish. The whole flake.nix is what distinguishes
      # repos, because description, toolchain and command map all differ, so the
      # whole flake.nix is what gets compared. Compared with bash's own
      # `$(<file)` rather than cmp or sha256sum, so the check depends on no
      # package at all -- pure builtins, correct even in a wrapper whose PATH
      # carries nothing but the repo's own toolchain.
      #
      # Consequence worth knowing: edit flake.nix and the dev-* wrappers in an
      # already-open `nix develop` stop recognising the tree, because they were
      # built from the previous flake.nix. That is a stale shell telling you so
      # -- re-enter it. `nix run` re-evaluates every time and never sees this.
      rootPreamble = ''
        SRC_ROOT=${lib.escapeShellArg "${self}"}
        export SRC_ROOT

        _dev_find_root() {
          local dir ref
          ref=$(<"$SRC_ROOT/flake.nix") || return 1
          dir=$(
            unset CDPATH
            cd -P -- "''${1:-.}" 2>/dev/null && pwd
          ) || return 1
          while [ -n "$dir" ]; do
            if [ -f "$dir/flake.nix" ] && [ "$(<"$dir/flake.nix")" = "$ref" ]; then
              printf '%s\n' "$dir"
              return 0
            fi
            dir=''${dir%/*}
          done
          return 1
        }

        REPO_ROOT="$(_dev_find_root "$PWD" || printf '%s\n' "$SRC_ROOT")"
        export REPO_ROOT
      '';

      # Wrappers only, not the shellHook -- an interactive shell has no business
      # carrying this function around. Any command text that writes files calls
      # it first, and it is the reason a mutating verb can fail loudly instead
      # of falling back to "well, the cwd then".
      #
      # The test is $REPO_ROOT != $SRC_ROOT, i.e. "rootPreamble found a real
      # checkout", not a permission or a store-path-prefix test. Both of those
      # answer a narrower question: a checkout may be read-only for unrelated
      # reasons, and a store path is not the only tree we must refuse to write.
      guardPreamble = ''
        need_writable_checkout() {
          if [ "$REPO_ROOT" != "$SRC_ROOT" ]; then
            return 0
          fi
          echo "''${0##*/}: this command rewrites files, so it needs a writable" >&2
          echo "checkout of this repo -- and standing in $PWD there is none: no" >&2
          echo "parent directory carries this flake's flake.nix. The only tree in" >&2
          echo "reach is the read-only store snapshot $SRC_ROOT, and rewriting" >&2
          echo "$PWD instead is exactly the bug this guard exists to prevent." >&2
          echo "cd into the repo (or \`nix develop\` it), or pass an explicit path." >&2
          exit 1
        }
      '';

      # One derivation per command, reused by both `apps` and the dev shell, so
      # the two can never diverge. `dev-` prefixed because a bare `test` binary
      # earlier on PATH would shadow the POSIX shell builtin and quietly break
      # every script in the repo that uses it.
      #
      # writeShellApplication, not writeShellScriptBin: it runs shellcheck at
      # BUILD time and sets `set -euo pipefail`, so an unquoted $@ or a silently
      # ignored failure is a `nix flake check` failure rather than a surprise in
      # front of an agent.
      wrappers =
        pkgs:
        lib.mapAttrs (
          name: cmd:
          pkgs.writeShellApplication {
            name = "dev-${name}";
            runtimeInputs = toolchain pkgs;
            runtimeEnv = envVars pkgs;
            meta.description = cmd.description;
            text = ''
              ${rootPreamble}
              ${guardPreamble}
              ${ldPreamble pkgs}
              ${cmd.text}
            '';
          }
        ) (commands pkgs);

      # `dev-help` is generated from the same attrset as everything else, so it
      # cannot describe a verb that does not exist or miss one that does. No
      # runtimeInputs: printing the map must work with nothing installed.
      helpFor =
        pkgs:
        let
          cmds = commands pkgs;
          names = lib.attrNames cmds;
          width = lib.foldl' (a: n: lib.max a (builtins.stringLength n)) 0 names;
          pad = n: n + lib.concatStrings (lib.genList (_: " ") (width - builtins.stringLength n));
          line = n: c: "  dev-${pad n}  ${c.description}";
        in
        pkgs.writeShellApplication {
          name = "dev-help";
          meta.description = "print this repo's command map (works offline)";
          text = ''
            cat <<'EOF'
            ${lib.concatStringsSep "\n" (lib.mapAttrsToList line cmds)}
            EOF
          '';
        };

      # The regression gate for rootPreamble and guardPreamble, which are the
      # two pieces of this flake that can silently damage a tree that is not
      # this repo. It tests the MECHANISM, not any verb, which is precisely what
      # makes it fleet-generic: it needs to know nothing about what this repo
      # does, only that the anchor resolves and the guard refuses.
      #
      # The decoy is a real directory carrying a real flake.nix that differs.
      # Marker-file anchors pass a decoy like this -- that is the whole point of
      # the probe -- and so does any anchor that trusts `pwd`. Probe 2 is the
      # other half, and without it a guard that refused everything would score a
      # perfect pass: a tree that IS byte-identical must still be adopted, or
      # every mutating verb in the repo is dead. Probe 3 pins the subdirectory
      # case, which is the normal one for an agent working inside a repo.
      #
      # A per-repo probe that drives the actual verbs is strictly better and
      # cannot live here -- it has to know which verb writes and which needs a
      # network. INTERFACE.md shows how to add one via `extraChecks`.
      anchorCheck =
        pkgs:
        pkgs.runCommand "anchor-check" { } ''
          set -euo pipefail

          # The two preambles under test, verbatim, in a file the probes source.
          # A quoted heredoc, so every $ below is the bash the wrappers see.
          cat > preamble.sh <<'CANONICAL_PREAMBLE_EOF'
          ${rootPreamble}
          ${guardPreamble}
          CANONICAL_PREAMBLE_EOF

          mkdir decoy
          printf '{\n  description = "a different repo";\n  outputs = _: { };\n}\n' > decoy/flake.nix
          printf 'do not touch me\n' > decoy/victim.txt
          cp -r decoy decoy.orig

          # ---- probe 1: a foreign tree must not be adopted ----
          if ! ( cd decoy && . ../preamble.sh && [ "$REPO_ROOT" = "$SRC_ROOT" ] ); then
            echo "anchor adopted a directory that is not this repo" >&2
            exit 1
          fi
          # In a subshell: need_writable_checkout ends in `exit`, which would
          # otherwise take this whole build down instead of failing a condition.
          if ( cd decoy && . ../preamble.sh && need_writable_checkout ) > guard.log 2>&1; then
            echo "need_writable_checkout accepted a tree that is not this repo" >&2
            exit 1
          fi
          if ! diff -r decoy decoy.orig; then
            echo "the probes modified the foreign tree" >&2
            exit 1
          fi

          # ---- probe 2: a byte-identical checkout must be adopted ----
          cp -r ${lib.escapeShellArg "${self}"} checkout
          chmod -R u+w checkout
          if ! ( cd checkout && . ../preamble.sh &&
                 [ "$REPO_ROOT" = "$(pwd -P)" ] && need_writable_checkout ); then
            echo "anchor refused a byte-identical checkout of this repo" >&2
            exit 1
          fi

          # ---- probe 3: from a subdirectory, still the checkout root ----
          mkdir -p checkout/probe3/deeper
          if ! ( cd checkout/probe3/deeper && . ../../../preamble.sh &&
                 [ "$REPO_ROOT" = "$(cd -P ../.. && pwd)" ] ); then
            echo "anchor did not walk up to the checkout root from a subdirectory" >&2
            exit 1
          fi

          touch "$out"
        '';
    in
    {
      # `nix flake show` -- the discovery entrypoint, and deliberately the whole
      # machine-facing contract: every app carries a meta.description, which
      # `nix flake show` prints inline and `nix flake show --json` exposes at
      # .apps.<system>.<name>.description. Pure evaluation, so an agent gets the
      # entire command map in one cheap call without reading a README.
      #
      # Do NOT invent a top-level output for this (`agentManifest`, `probeThing`
      # ...). Nix answers with `warning: unknown flake output '<name>'` on every
      # single `nix flake check`, forever.
      apps = forAllSystems (
        pkgs:
        lib.mapAttrs (name: cmd: {
          type = "app";
          program = "${(wrappers pkgs).${name}}/bin/dev-${name}";
          meta.description = cmd.description;
        }) (commands pkgs)
      );

      # `nix develop` -- the toolchain, plus a dev-<verb> for every app.
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = toolchain pkgs ++ lib.attrValues (wrappers pkgs) ++ [ (helpFor pkgs) ];

          env = envVars pkgs;

          # Natively-compiled extension modules are routinely built at -O0,
          # where glibc's _FORTIFY_SOURCE stops being a warning and becomes a
          # hard error.
          hardeningDisable = [ "fortify" ];

          shellHook = ''
            # mkShell inherits SOURCE_DATE_EPOCH=315532800 (1980-01-01) from
            # stdenv, and any wheel or zip built in here then dies with "ZIP does
            # not support timestamps before 1980".
            unset SOURCE_DATE_EPOCH

            # $REPO_ROOT and $SRC_ROOT are exported here as a convenience for
            # the human at the prompt. Every wrapper re-resolves them from
            # scratch and none of them reads these, on purpose: a stale value
            # exported by one repo's shell must never steer another repo's verb.
            ${rootPreamble}
            ${ldPreamble pkgs}

            # Nothing networked, nothing stateful and nothing interactive above
            # this line, and nothing below it either. No environment
            # bootstrapping, no dependency installation, no `read`, no
            # `exec $SHELL`. Bootstrapping in the hook makes a cold
            # `nix develop -c <anything>` start downloading before it runs
            # anything, on EVERY invocation -- the exact failure an unattended
            # agent cannot diagnose. That is what a `setup` verb is for.

            # The banner is interactive-only, and this guard is load-bearing:
            # shellHook output lands on the STDOUT of `nix develop -c <cmd>`, so
            # an unguarded echo corrupts anything parsing it
            # (`nix develop -c cat x.json | jq` fails to parse). $- is the only
            # reliable discriminator here -- it lacks `i` for `nix develop -c`
            # and has it at an interactive prompt. Do not test $PS1 (unset in
            # both) or $IN_NIX_SHELL (set in both). >&2 is the second layer, for
            # the case where a caller runs us on a pty.
            case $- in
              *i*) echo "${repoName} dev shell -- 'dev-help' for the command map" >&2 ;;
            esac
          '';
        };
      });

      # `nix flake check` -- honest by construction, and the only gate this
      # style has. `toolchain` realises the whole toolchain closure (so a typo'd
      # or currently-broken attr fails here, not halfway through a task) and
      # builds every wrapper, which runs shellcheck over every command text.
      # `anchoring` is the regression test described above.
      #
      # Repo-specific checks go in `extraChecks`, never here. They may not
      # shadow either canonical name: silently replacing `anchoring` with
      # something weaker is the exact failure this whole file exists to make
      # impossible, so a collision is an eval error with both names in it.
      #
      # NEVER add a check that always passes. An agent reads "all checks
      # passed!" as a signal, and a fake check makes `nix flake check` a liar.
      checks = forAllSystems (
        pkgs:
        let
          canonical = {
            toolchain =
              pkgs.runCommand "toolchain-check"
                {
                  nativeBuildInputs = toolchain pkgs ++ lib.attrValues (wrappers pkgs) ++ [ (helpFor pkgs) ];
                }
                ''
                  set -euo pipefail
                  dev-help > help.txt

                  # A while-read over a heredoc rather than `for x in <list>`,
                  # which is a bash syntax error when the list is empty -- and a
                  # repo with no verbs yet is a legitimate state.
                  while IFS= read -r verb; do
                    [ -n "$verb" ] || continue
                    command -v "dev-$verb" > /dev/null || {
                      echo "dev-$verb is not on PATH" >&2
                      exit 1
                    }
                    grep -q -- "dev-$verb" help.txt || {
                      echo "dev-$verb is missing from the dev-help map" >&2
                      exit 1
                    }
                  done <<'CANONICAL_VERBS_EOF'
                  ${lib.concatStringsSep "\n" (lib.attrNames (commands pkgs))}
                  CANONICAL_VERBS_EOF

                  touch "$out"
                '';
            anchoring = anchorCheck pkgs;
          };
          extra = extraChecks pkgs;
          clash = lib.intersectLists (lib.attrNames canonical) (lib.attrNames extra);
        in
        if clash != [ ] then
          throw "extraChecks must not redefine canonical checks: ${lib.concatStringsSep ", " clash}"
        else
          canonical // extra
      );

      # `nix fmt` -- formats the *Nix* in this repo; project code gets a `fmt`
      # verb. nixfmt-tree (the treefmt wrapper) rather than bare nixfmt, because
      # bare nixfmt tries to parse every path handed to it and fails on non-Nix
      # files. This file ships already formatted, so `nix fmt` is a no-op rather
      # than a diff across the fleet.
      #
      # This is the one verb here NOT anchored to $REPO_ROOT, and it cannot be:
      # `nix fmt` is nix's own verb, and nix -- not this flake -- decides which
      # paths the formatter receives, passing the cwd when the user names none.
      # A wrapper that overrode them would break `nix fmt path/to/one/file.nix`,
      # and it cannot tell that "." apart from the default. So `nix fmt` formats
      # where you stand, by design; the `fmt` verb is the anchored one.
      formatter = forAllSystems (pkgs: pkgs.nixfmt-tree);
    };
}
# >>>>> END CANONICAL MACHINERY v1 <<<<<
