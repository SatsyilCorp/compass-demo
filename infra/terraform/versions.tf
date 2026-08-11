terraform {
  required_version = ">= 1.7.0"

  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      "compass:component"      = "document-ml"
      "compass:environment"    = var.environment
      "compass:synthetic-only" = "true"
      "managed-by"             = "terraform"
    }
  }
}
