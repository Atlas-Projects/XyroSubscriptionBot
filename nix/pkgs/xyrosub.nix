{ poetry2nix
, python
, pythonPackages
, projectDir
}:

poetry2nix.mkPoetryApplication {
  inherit projectDir python;
  preferWheels = true;
}
