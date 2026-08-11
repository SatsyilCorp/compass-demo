output "document_ml_function_name" {
  description = "Document and MLOps Lambda function."
  value       = aws_lambda_function.document_ml.function_name
}

output "document_ml_table_name" {
  description = "Durable document and model evidence ledger."
  value       = aws_dynamodb_table.document_ml.name
}

output "document_ml_state_machine_arn" {
  description = "Event-driven bronze, silver, gold, and quarantine workflow."
  value       = aws_sfn_state_machine.document_ml.arn
}

output "document_model_package_group_name" {
  description = "SageMaker registry group for approved model packages."
  value       = aws_sagemaker_model_package_group.document_classifier.model_package_group_name
}
