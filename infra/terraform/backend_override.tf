# Plan-only override for CI: the golden pipeline runs `tofu init` with no
# backend-config values and no -input flag, so the empty s3 partial backend
# in versions.tf makes init prompt interactively and hang the runner. This
# override swaps in a local backend for validate/plan runs. The controlled
# deploy workflow removes this file before its own init, which supplies the
# real s3 backend configuration.
terraform {
  backend "local" {}
}
