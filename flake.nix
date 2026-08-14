{
  # Keep this line accurate and one line long: `nix flake metadata` prints it,
  # and it is the first thing a cold agent learns about the repo.
  description = "dc-bot -- OpenAI-backed Discord DM bot (discord.py, Pillow receipt faking). Run `nix flake show` for the command map.";

  # nixpkgs is the only input, on purpose.
  #
  # flake-utils would buy exactly one thing here -- eachDefaultSystem -- which is
  # the three-line genAttrs below. In exchange it costs a second lock node in
  # every repo (flake-utils transitively pulls `systems`, so really two), a
  # second upstream that can break one repo and not the others, and a hardcoded
  # system list this repo cannot edit. That list is currently broken: it still
  # contains x86_64-darwin, which now throws (see `systems` below).
  #
  # nixos-unstable is the same channel the author's own NixOS config tracks, so
  # `nix develop` here and `nixos-rebuild` there resolve the same store paths and
  # share one cache.
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    # `...` rather than a closed { self, nixpkgs }: adding a second input later
    # would otherwise fail with "called with unexpected argument 'self'".
    #
    # `self` is taken because rootPreamble needs it: it is the only handle a
    # store-resident wrapper has on "the repo this flake came from". See the
    # anchor in that preamble.
    { self, nixpkgs, ... }:
    let
      lib = nixpkgs.lib;

      # x86_64-darwin is deliberately absent. nixpkgs 26.11 replaced that whole
      # attribute set with `throw "Nixpkgs 26.11 has dropped support for
      # x86_64-darwin"`. genAttrs is lazy, so plain `nix develop` on Linux would
      # not notice -- it detonates later, on `nix flake check --all-systems`.
      # Add it back only against a separate nixpkgs-26.05-darwin input.
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];

      # Stand-in for flake-utils.lib.eachDefaultSystem. Passes `pkgs` rather than
      # a system string, because that is what every call site below wants.
      forAllSystems = f: lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      # ======================================================================
      # PER-REPO BLOCK 1 -- the toolchain
      # ======================================================================
      # Everything the commands below need. `nix flake check` realises this
      # closure, so a typo'd attr name fails at the flake gate instead of
      # surfacing as "command not found" halfway through a task.
      #
      # Explicit `pkgs.foo`, never `with pkgs; [ ... ]`: when an attr disappears
      # in a nixpkgs bump, `with` reports a bare undefined identifier with no
      # hint of which set it came from, and the name is not greppable.
      #
      # python313 rather than python3: the Dockerfile this repo actually deploys
      # from is `FROM python:3.13-slim`, so the dev shell matches production. A
      # rolling `python3` alias would also invalidate .venv on every nixpkgs bump.
      toolchain = pkgs: [
        # ---- this repo's ecosystem ----
        pkgs.python313
        pkgs.uv
        pkgs.ruff

        # ---- present in every repo in the fleet ----
        pkgs.git
        pkgs.jq
        pkgs.gnumake
      ];

      # ======================================================================
      # PER-REPO BLOCK 2 -- libraries that get dlopened, not linked
      # ======================================================================
      # manylinux wheels carry .so files that are dlopened at runtime, so neither
      # patchelf nor the nix linker ever sees them and NixOS has no /usr/lib for
      # them to find. stdenv.cc.cc.lib supplies libstdc++; zlib is what the
      # Pillow wheel reaches for when it decodes the PNG receipt template. Keep
      # this list minimal -- LD_LIBRARY_PATH is a blunt instrument.
      nativeLibs = pkgs: [
        pkgs.stdenv.cc.cc.lib
        pkgs.zlib
      ];

      # ======================================================================
      # PER-REPO BLOCK 3 -- constant environment variables
      # ======================================================================
      # Only values that are constants belong here. Anything that must READ an
      # existing value (LD_LIBRARY_PATH), UNSET something (SOURCE_DATE_EPOCH) or
      # touch the work tree goes in the shellHook further down.
      #
      # This attrset is applied to BOTH surfaces -- the dev shell and every
      # `nix run` wrapper -- so a command cannot behave differently depending on
      # how it was invoked.
      #
      # Deliberately absent: DISCORD_TOKEN, OPENAI_API_KEY, CHANNEL_ID, GUILD_ID,
      # STREAMER_NAME, ADMIN_PASSWORD. bot_start.py demands those six at startup
      # and they are secrets -- they belong in the caller's environment, never in
      # a world-readable /nix/store path.
      envVars = pkgs: {
        # Keep uv on the nix interpreter. Left alone it downloads its own
        # portable CPython, which then resolves a different set of wheels than
        # this shell pins: two Pythons, one venv, no way to tell which is live.
        UV_PYTHON = "${pkgs.python313}/bin/python";
        UV_PYTHON_DOWNLOADS = "never";
        # /nix/store and the work tree are usually different filesystems, so
        # uv's default hardlink strategy warns on every single install.
        UV_LINK_MODE = "copy";
        PIP_DISABLE_PIP_VERSION_CHECK = "1";
        # Matches the Dockerfile's ENV PYTHONUNBUFFERED=1. This bot logs its way
        # through a conversation, and a buffered stdout hides the log lines an
        # agent is waiting on until the process exits.
        PYTHONUNBUFFERED = "1";
      };

      # ======================================================================
      # PER-REPO BLOCK 4 -- the command map
      # ======================================================================
      # THE single source of truth. It generates `apps` (so `nix run .#test`
      # works), the `dev-*` wrappers on PATH inside the shell, and `dev-help`.
      # Nothing is written twice, so `nix flake show` can never disagree with
      # what `dev-test` actually runs.
      #
      # `build` is deliberately absent: this repo produces no local artifact.
      # The deployable is a container image, and .github/workflows/build_and_push.yml
      # builds it with `docker build` against a daemon nix cannot supply. A
      # `build` verb here would only be able to lie about that.
      #
      # `text` is bash under `set -euo pipefail` and shellcheck'd at BUILD time.
      #
      # THE ANCHORING INVARIANT, and it is not negotiable: a verb behaves the
      # same no matter which directory it was invoked from, and never reads or
      # writes a file outside this repo. So no verb may end in a bare "$@" --
      # every tool here treats "no paths given" as "do it to the current
      # directory", and the current directory belongs to the caller, not to us.
      # `nix run /path/to/dc-bot#lint` from elsewhere used to print "All checks
      # passed!" (zero files inspected) and `#fmt` used to REWRITE whatever
      # happened to be sitting in the caller's cwd.
      #
      # Anchor with whatever form the tool actually accepts: `cd "$REPO_ROOT"`
      # plus an explicit `.` for ruff, `cd` alone for a tool that insists on
      # relative patterns. Explicit user arguments still win, so
      # `nix run .#fmt -- bot.py` keeps working -- paths are then resolved from
      # the repo root, which is also where an agent almost always already is.
      # Uncommitted edits are still what gets linted and formatted: the anchor
      # prefers the live work tree, and only falls back to the flake's own
      # snapshot when the caller is nowhere near a checkout.
      commands = pkgs: {
        setup = {
          # pytest is installed alongside requirements.txt on purpose: the repo
          # ships five real pytest files (test_utils, test_identity,
          # test_bot_identity, test_bot_completion, test_welcome_cancel) but
          # requirements.txt lists runtime deps only, and there is no
          # requirements-dev.txt to add it to without touching the repo's own
          # dependency contract.
          #
          # --allow-existing, because without it uv treats "a .venv is already
          # here" as a hard error ("A virtual environment already exists at:
          # .venv") and exits 2 under `set -e` BEFORE `uv pip install` ever runs.
          # That made the bootstrap verb fail on exactly the trees that need it
          # most: every clone that has already been set up once, i.e. every
          # re-run after a requirements.txt change and every agent retry loop.
          # With the flag the venv is reused and the install re-resolves, so this
          # verb is now idempotent -- run it as often as you like.
          description = "(network) create/update .venv from requirements.txt, plus pytest for the test suite";
          text = ''
            uv venv --allow-existing "$REPO_ROOT/.venv"
            uv pip install --python "$REPO_ROOT/.venv/bin/python" -r "$REPO_ROOT/requirements.txt" pytest
          '';
        };
        test = {
          # The venv interpreter by absolute path, not a bare `pytest`. The
          # wrappers prepend the nix toolchain to PATH, so a bare name would
          # resolve to the store copy and miss discord.py, openai and Pillow.
          #
          # $REPO_ROOT is passed as pytest's target so the suite is found (and
          # .pytest_cache lands at the repo root) even when an agent invokes this
          # from a subdirectory. The tests themselves monkeypatch.chdir into a
          # tmp_path, so they never write into the work tree.
          #
          # This one already satisfied the anchoring invariant -- it names its
          # target instead of trailing a bare "$@" -- so it is unchanged. Note
          # "$REPO_ROOT" "$@" and not "''${@:-$REPO_ROOT}": extra pytest flags
          # (`-- -q -k welcome`) have to compose with the target, not replace it.
          description = "run the pytest suite (needs `setup` first)";
          text = ''"$REPO_ROOT/.venv/bin/python" -m pytest "$REPO_ROOT" "$@"'';
        };
        lint = {
          # The repo ships no pyproject.toml/ruff.toml, so this runs ruff's own
          # default rule set and currently reports 61 PRE-EXISTING findings
          # (mostly UP032 f-string, I001 import order, BLE001 blind except) and
          # therefore exits 1 on an untouched checkout. That is the honest state
          # of the code, not a broken flake -- do not "fix" it by weakening the
          # command. Compare against `git stash` output before blaming a change.
          #
          # `cd` + an explicit `.` rather than a bare "$@": ruff with no path
          # argument lints the process's cwd, so invoked by flake URL from any
          # other directory this reported on the CALLER's files -- normally none
          # of them Python, hence a green "All checks passed!" from a gate that
          # had inspected nothing. The cd also covers the flags-only case
          # (`-- --statistics`), which a bare `"''${@:-$REPO_ROOT}"` would not.
          #
          # --no-cache when the anchor is not writable: ruff puts .ruff_cache
          # next to the files it inspects, so on the snapshot anchor it aborted
          # with "Failed to initialize cache ... Read-only file system" and exit
          # 2 -- a gate that dies before looking at anything, which is the same
          # lie as before wearing a different exit code. Nothing is lost: the
          # snapshot path changes with its content, so its cache is never reused.
          description = "ruff check the whole repo (exits 1 on the pre-existing findings)";
          text = ''
            cd "$REPO_ROOT"
            cache=()
            [ -w "$REPO_ROOT" ] || cache=(--no-cache)
            ruff check "''${cache[@]}" "''${@:-.}"
          '';
        };
        fmt = {
          # Formats the whole tree, which currently rewrites 11 of 22 files.
          # Pass explicit paths (`nix run .#fmt -- bot.py`, resolved from the
          # repo root) to keep a diff reviewable, or `-- --check` to see what it
          # would touch.
          #
          # Anchored exactly like lint, and this is the half that actually did
          # damage: ruff format MUTATES. Invoked by flake URL from an unrelated
          # directory, the old bare "$@" rewrote that directory's Python files.
          #
          # The guard is for the snapshot anchor in rootPreamble: if we fell back
          # to the store there is no work tree to format, and refusing with one
          # line beats 11 "Permission denied"s. It asks the actual question --
          # can I write here? -- rather than matching /nix/store/*, so a
          # read-only checkout gets the same clean refusal.
          description = "ruff format the whole repo (rewrites files)";
          text = ''
            if [ ! -w "$REPO_ROOT" ]; then
              echo "dev-fmt: $REPO_ROOT is not writable -- run this from inside a dc-bot checkout" >&2
              exit 1
            fi
            cd "$REPO_ROOT"
            ruff format "''${@:-.}"
          '';
        };
        run = {
          # lint and fmt cd for anchoring; this one cd's because the CODE needs
          # it. Every persistence path (persistence/, persistence/logs/,
          # persistence/media/) is cwd-relative, exactly as in the container
          # where WORKDIR is /app. Without the cd, starting the bot from a
          # subdirectory would silently fork a second set of conversation files.
          #
          # run.sh is bypassed deliberately -- it decodes WHITE_LIST/BLACK_LIST
          # into hardcoded /app/persistence paths that do not exist outside the
          # image. Write persistence/whitelist_<BOT_NAME>.json by hand locally.
          description = "(network) start the bot -- needs DISCORD_TOKEN, OPENAI_API_KEY, CHANNEL_ID, GUILD_ID, STREAMER_NAME, ADMIN_PASSWORD";
          text = ''
            cd "$REPO_ROOT"
            exec "$REPO_ROOT/.venv/bin/python" bot_start.py "$@"
          '';
        };
      };

      # ======================================================================
      # PER-REPO BLOCK 5 -- the work-tree fingerprint
      # ======================================================================
      # A path that exists at the root of a dc-bot checkout and is tracked, so
      # it is present in a fresh clone and in the flake snapshot alike.
      # rootPreamble uses it to answer "is the git work tree I just found
      # actually THIS repo?", because `git rev-parse --show-toplevel` answers
      # just as cheerfully from inside somebody else's checkout, and acting on
      # that answer is how a `fmt` verb rewrites a stranger's files.
      #
      # bot_start.py is the entrypoint `run` already execs, so it cannot vanish
      # without this flake needing an edit anyway.
      repoMarker = "bot_start.py";

      # ======================================================================
      # GENERIC MACHINERY -- byte-identical in all 41 repos, do not edit
      # ======================================================================

      # Prepend, never assign: a host LD_LIBRARY_PATH may be carrying something
      # the user needs, and clobbering it breaks binaries they launch from here.
      # Linux only -- on darwin the loader variable is DYLD_*, and exporting a
      # Linux-shaped value there is at best useless.
      ldPreamble =
        pkgs:
        lib.optionalString (pkgs.stdenv.hostPlatform.isLinux && nativeLibs pkgs != [ ]) ''
          export LD_LIBRARY_PATH="${lib.makeLibraryPath (nativeLibs pkgs)}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        '';

      # Every command gets $REPO_ROOT, and every command anchors itself to it --
      # see THE ANCHORING INVARIANT in block 4. `nix run` and `nix develop` both
      # start in whatever directory they were invoked from, and a wrapper living
      # in /nix/store has no way to learn which clone launched it, so the anchor
      # is resolved here, once, and only two things can win:
      #
      #   1. the enclosing git work tree, but ONLY if repoMarker is in it. The
      #      marker is the load-bearing half. The previous fallback was
      #      `|| pwd`, which pointed every verb at the caller's directory
      #      whenever that directory was outside git -- silent for `lint`,
      #      destructive for `fmt` -- and a rev-parse without the marker check
      #      would do the same inside an unrelated checkout.
      #   2. ${self}, this flake's own source in the store. Same content as the
      #      work tree (nix copies the tracked files, dirty ones included), so
      #      `lint` still reports the truth about the right files from anywhere,
      #      and because /nix/store is read-only there is no way for a mutating
      #      verb to write outside the repo -- it refuses or it fails.
      #
      # Deliberately NOT honouring an inherited $REPO_ROOT: the dev shell exports
      # one, and a shell entered by flake URL from outside the repo would then
      # pin every later `dev-fmt` to the snapshot even after you cd into the real
      # checkout. Each wrapper re-deriving the anchor is what makes the two
      # surfaces agree.
      #
      # Naming `self` here is what ties the wrapper derivations to the source, so
      # editing a tracked file re-derives them. They are five shellcheck runs on
      # five short scripts; a couple of seconds is the price of the anchor.
      rootPreamble = ''
        REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
        if [ ! -e "$REPO_ROOT/${repoMarker}" ]; then
          REPO_ROOT="${self}"
        fi
        export REPO_ROOT
      '';

      # One derivation per command, reused by both `apps` and the dev shell, so
      # the two can never diverge. `dev-` prefixed because a bare `test` binary
      # earlier on PATH would shadow the POSIX shell builtin and quietly break
      # every script in the repo that uses it.
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
              ${ldPreamble pkgs}
              ${cmd.text}
            '';
          }
        ) (commands pkgs);

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

          # Some C extensions and node-gyp addons compile at -O0, where glibc's
          # _FORTIFY_SOURCE becomes a hard error instead of a warning.
          hardeningDisable = [ "fortify" ];

          shellHook = ''
            # mkShell inherits SOURCE_DATE_EPOCH=315532800 (1980-01-01) from
            # stdenv, and any wheel or zip built in here then dies with "ZIP does
            # not support timestamps before 1980".
            unset SOURCE_DATE_EPOCH

            ${rootPreamble}
            ${ldPreamble pkgs}

            # Nothing networked, nothing stateful and nothing interactive above
            # this line, and nothing below it either. No venv creation, no
            # `pip install`. Bootstrapping in the hook makes a cold
            # `nix develop -c pytest` start downloading before it runs anything,
            # on EVERY invocation -- the exact failure an unattended agent cannot
            # diagnose. That is what `dev-setup` is for.

            # The banner is interactive-only, and this guard is load-bearing:
            # shellHook output lands on the STDOUT of `nix develop -c <cmd>`, so
            # an unguarded echo corrupts anything parsing it
            # (`nix develop -c cat x.json | jq` fails to parse). $- is the only
            # reliable discriminator here -- it lacks `i` for `nix develop -c`
            # and has it at an interactive prompt. Do not test $PS1 (unset in
            # both) or $IN_NIX_SHELL (set in both). >&2 is the second layer, for
            # the case where a caller runs us on a pty.
            case $- in
              *i*) echo "dc-bot dev shell -- 'dev-help' for the command map" >&2 ;;
            esac
          '';
        };
      });

      # `nix flake check` -- honest by construction. It realises the toolchain
      # closure (so a typo'd or currently-broken attr fails here) and builds
      # every wrapper, which runs shellcheck over every command text. Add real
      # test derivations beside it. NEVER add a check that always passes: an
      # agent reads "all checks passed!" as a signal, and a fake check makes
      # `nix flake check` a liar.
      #
      # The pytest suite is NOT a check: it needs the .venv that `dev-setup`
      # populates over the network, and a nix build has no network.
      checks = forAllSystems (pkgs: {
        toolchain =
          pkgs.runCommand "toolchain-check"
            {
              nativeBuildInputs = toolchain pkgs ++ lib.attrValues (wrappers pkgs);
            }
            ''
              for verb in ${lib.escapeShellArgs (lib.attrNames (commands pkgs))}; do
                command -v "dev-$verb" > /dev/null || {
                  echo "dev-$verb is not on PATH" >&2
                  exit 1
                }
              done
              touch "$out"
            '';
      });

      # `nix fmt` -- formats the *Nix* in this repo; project code is `dev-fmt`.
      # nixfmt-tree (the treefmt wrapper) rather than bare nixfmt, because bare
      # nixfmt tries to parse every path handed to it and fails on non-Nix files.
      # This file ships already formatted, so `nix fmt` is a no-op rather than a
      # diff in 41 repos.
      formatter = forAllSystems (pkgs: pkgs.nixfmt-tree);
    };
}
