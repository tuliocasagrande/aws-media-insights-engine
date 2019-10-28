# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import boto3
import urllib3
import json
from MediaInsightsEngineLambdaHelper import MediaInsightsOperationHelper
from MediaInsightsEngineLambdaHelper import MasExecutionError
from MediaInsightsEngineLambdaHelper import DataPlane

region = os.environ['AWS_REGION']
textract = boto3.client("textract")

def lambda_handler(event, context):
    operator_object = MediaInsightsOperationHelper(event)
    
    try:
        job_id = operator_object.metadata["TextractJobId"]
        workflow_id = operator_object.workflow_execution_id
        asset_id = operator_object.asset_id
    except KeyError as e:
        operator_object.update_workflow_status("Error")
        operator_object.add_workflow_metadata(TextractError="Missing a required metadata key {e}".format(e=e))
        raise MasExecutionError(operator_object.return_output_object())
    
    dataplane = DataPlane()

    args = {'JobId': job_id}

    while True:
        try:
            response = textract.get_document_analysis(
                **args
            )
            print(response)
        except Exception as e:
            operator_object.update_workflow_status("Error")
            operator_object.add_workflow_metadata(TextractError=str(e), TextractJobId=job_id)
            raise MasExecutionError(operator_object.return_output_object())
        else:
            if response["JobStatus"] == "IN_PROGRESS":
                operator_object.update_workflow_status("Executing")
                operator_object.add_workflow_metadata(TextractJobId=job_id, AssetId=asset_id, WorkflowExecutionId=workflow_id)
                return operator_object.return_output_object()
            elif response["JobStatus"] == "FAILED":
                operator_object.update_workflow_status("Error")
                operator_object.add_workflow_metadata(TextractJobId=job_id,
                                                TextractError=str("Unable to upload metadata for asset: {asset}".format(asset=asset_id)))
                raise MasExecutionError(operator_object.return_output_object())
            elif response["JobStatus"] == "SUCCEEDED" or response["JobStatus"] == "PARTIAL_SUCCESS" :
                metadata_upload = dataplane.store_asset_metadata(asset_id, operator_object.name, workflow_id, response, paginate=True)
                if "Status" not in metadata_upload:
                    operator_object.update_workflow_status("Error")
                    operator_object.add_workflow_metadata(
                        TextractError="Unable to upload metadata for asset: {asset}".format(asset=asset_id),
                        TextractJobId=job_id)
                    raise MasExecutionError(operator_object.return_output_object())
                else:
                    if metadata_upload["Status"] == "Success":
                        print("Uploaded metadata for asset: {asset}".format(asset=asset_id))
                    else:
                        operator_object.update_workflow_status("Error")
                        operator_object.add_workflow_metadata(
                            TextractError="Unable to upload metadata for asset: {asset}".format(asset=asset_id),
                            TextractJobId=job_id)
                        raise MasExecutionError(operator_object.return_output_object())

                    if 'NextToken' in response:
                        args['NextToken'] = response['NextToken']
                    else:
                        # Persist Textract results
                        metadata_upload = dataplane.store_asset_metadata(asset_id, operator_object.name, workflow_id, response,
                                                                        paginate=True, end=True)

                        if "Status" not in metadata_upload:
                            operator_object.update_workflow_status("Error")
                            operator_object.add_workflow_metadata(
                                TextractError="Unable to upload metadata for {asset}: {error}".format(asset=asset_id,
                                                                                                            error=metadata_upload))
                            raise MasExecutionError(operator_object.return_output_object())
                        else:
                            if metadata_upload["Status"] == "Success":
                                print("Uploaded metadata for asset: {asset}".format(asset=asset_id))
                                operator_object.add_workflow_metadata(TextractJobId=job_id)
                                operator_object.update_workflow_status("Complete")
                                return operator_object.return_output_object()
                            else:
                                operator_object.update_workflow_status("Error")
                                operator_object.add_workflow_metadata(
                                    TextractError="Unable to upload metadata for asset: {asset}".format(asset=asset_id))
                                raise MasExecutionError(operator_object.return_output_object())
                        break

    