{
  description = "Master thesis (IPB/UTFPR) – LuaLaTeX + DOCX build";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f:
        nixpkgs.lib.genAttrs systems
          (system: f (import nixpkgs { inherit system; }));

      # ── toolchains ───────────────────────────────────────────────────────
      tex        = pkgs: pkgs.texlive.combined.scheme-full;
      pdfInputs  = pkgs: [ (tex pkgs) pkgs.perl ];
      docxInputs = pkgs: [ pkgs.pandoc pkgs.python3 pkgs.bash ];

      # ── shared prologue ─────────────────────────────────────────────────
      prologue = ''
        : "''${PROJECT_ROOT:=$PWD}"
        if [ ! -f "$PROJECT_ROOT/main.tex" ]; then
          echo "error: main.tex not found in $PROJECT_ROOT" >&2
          echo "       (set PROJECT_ROOT or run from the thesis repo root)" >&2
          exit 1
        fi
        cd "$PROJECT_ROOT"
      '';

      # ── the three commands, packaged with their command names ──────────
      mkScripts = pkgs: {
        pdf = pkgs.writeShellApplication {
          name = "pdf";
          runtimeInputs = pdfInputs pkgs;
          text = ''
            ${prologue}
            exec latexmk "$@"
          '';
        };

        clean = pkgs.writeShellApplication {
          name = "clean";
          runtimeInputs = pdfInputs pkgs;
          text = ''
            ${prologue}
            rm -rf build/
            echo "cleaned $PROJECT_ROOT/build"
          '';
        };

        docx = pkgs.writeShellApplication {
          name = "docx";
          runtimeInputs = (pdfInputs pkgs) ++ (docxInputs pkgs);
          text = ''
            ${prologue}
            exec bash scripts/build-docx.sh "$@"
          '';
        };
      };
    in
    {
      # nix build .#pdf  /  .#clean  /  .#docx
      packages = forAllSystems (pkgs:
        let s = mkScripts pkgs; in {
          default = s.pdf;
          inherit (s) pdf clean docx;
        });

      # nix run .#pdf  /  .#clean  /  .#docx
      apps = forAllSystems (pkgs:
        let s = mkScripts pkgs; in {
          default = { type = "app"; program = "${s.pdf}/bin/pdf"; };
          pdf     = { type = "app"; program = "${s.pdf}/bin/pdf"; };
          clean   = { type = "app"; program = "${s.clean}/bin/clean"; };
          docx    = { type = "app"; program = "${s.docx}/bin/docx"; };
        });

      # `pdf`, `clean`, `docx` are on PATH inside `nix develop` / direnv
      devShells = forAllSystems (pkgs:
        let s = mkScripts pkgs; in {
          default = pkgs.mkShell {
            packages =
              (pdfInputs pkgs)
              ++ (docxInputs pkgs)
              ++ [ s.pdf s.clean s.docx ];
            shellHook = ''
              echo "commands: pdf | clean | docx   (or nix run .#[pdf|clean|docx])"
            '';
          };
        });
    };
}
