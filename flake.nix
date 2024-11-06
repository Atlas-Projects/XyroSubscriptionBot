{
  description = "Flake for XyroSubBot";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    poetry2nix.url = "github:nix-community/poetry2nix";
    nix-filter.url = "github:numtide/nix-filter";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    nix-filter,
    ...
  }@inputs: flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = import nixpkgs { inherit system; };
      poetry2nix = inputs.poetry2nix.lib.mkPoetry2Nix { inherit pkgs; };

      python = pkgs.python312;
      pythonPackages = pkgs.python312Packages;
      projectDir = { forEnv }:
        nix-filter {
          name = "XyroSub";
          root = ./.;
          include = [
            "pyproject.toml"
            "poetry.lock"
          ] ++ pkgs.lib.optionals (!forEnv) [
            ./XyroSub
          ];
        };
    in
    with pkgs; {

      devShells.default = (
        (poetry2nix.mkPoetryEnv {
          inherit python;
          projectDir = projectDir { forEnv = true; };
          preferWheels = true;
        }).env.overrideAttrs (oldAttrs: {
          name = "XyroSub-dev";
          nativeBuildInputs = oldAttrs.nativeBuildInputs ++ [
            basedpyright
            ruff
            poetry
            pythonPackages.ipython
          ];
        })
      );

      packages = rec {
        XyroSub = (
          callPackage ./nix/pkgs/xyrosub.nix {
            inherit poetry2nix python pythonPackages;
            projectDir = projectDir { forEnv = false; };
          }
        );
        default = XyroSub;
      };

    });
}
