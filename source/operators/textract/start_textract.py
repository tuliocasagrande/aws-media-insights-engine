# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import boto3

from MediaInsightsEngineLambdaHelper import MediaInsightsOperationHelper
from MediaInsightsEngineLambdaHelper import MasExecutionError

region = os.environ['AWS_REGION']
textract = boto3.client("textract")

def lambda_handler(event, context):
        valid_types = [".png", ".jpg", ".pdf", ".jpeg"]
        optional_settings = {}

        operator_object = MediaInsightsOperationHelper(event)
        workflow_id = str(operator_object.workflow_execution_id)
        job_id = "textract" + "-" + workflow_id

        # Adding in exception block for now since we aren't guaranteed an asset id will be present, should remove later
        try:
            asset_id = operator_object.asset_id
        except KeyError as e:
            print("No asset id passed in with this workflow", e)
            asset_id = ''

        try:
            bucket = operator_object.input["Media"]["Image"]["S3Bucket"]
            key = operator_object.input["Media"]["Image"]["S3Key"]
            file_type = key.split('.')[-1]
        except Exception:
            operator_object.update_workflow_status("Error")
            operator_object.add_workflow_metadata(TextractError="No valid inputs")
            raise MasExecutionError(operator_object.return_output_object())
        
        if file_type not in valid_types:
            operator_object.update_workflow_status("Error")
            operator_object.add_workflow_metadata(TextractError="Not a valid file type")
            raise MasExecutionError(operator_object.return_output_object())

        media_file = 'https://s3.' + region + '.amazonaws.com/' + bucket + '/' + key

        try:
            response = textract.start_document_analysis(
                    DocumentLocation={
                    'S3Object': {
                        'Bucket': bucket,
                        'Name': key
                    }
                },
                FeatureTypes=[
                    'TABLES',
                    'FORMS'
                ]           
            )
            print(response)
        except Exception as e:
            operator_object.update_workflow_status("Error")
            operator_object.add_workflow_metadata(textract_error=str(e))
            raise MasExecutionError(operator_object.return_output_object())
        else:
            operator_object.update_workflow_status("Executing")
            operator_object.add_workflow_metadata(TextractJobId=response['JobId'], AssetId=asset_id, WorkflowExecutionId=workflow_id)
            return operator_object.return_output_object()
