###############################################################################
# PURPOSE:
#   Lambda function to perform Rekognition tasks on batches of image files
#   calling Rekognition Content Moderation API
#   It reads a list of frames from a json file - result of frame extraction Lambda
#   WARNING: This function might needs longer Lambda timeouts depending on how many frames should be proceesd.
###############################################################################

import os
import json
import urllib
import boto3
import uuid
from MediaInsightsEngineLambdaHelper import MediaInsightsOperationHelper
from MediaInsightsEngineLambdaHelper import MasExecutionError
from MediaInsightsEngineLambdaHelper import DataPlane


s3 = boto3.client('s3')

# Perform Content Moderation analysis in an image
def detect_moderation_labels(bucket, key):
    rek = boto3.client('rekognition')
    try:
        response = rek.detect_moderation_labels(Image={'S3Object': {'Bucket': bucket, 'Name': key}}, MinConfidence=40)
    except Exception as e:
        return Exception(e)
    else:
        return response

# Lambda function entrypoint:
def lambda_handler(event, context):
    print("We got the following event:\n", event)
    output_object = MediaInsightsOperationHelper(event)
    try:
        if "Images" in event["Input"]["Media"]:
            s3bucket = event["Input"]["Media"]["Images"]["S3Bucket"]
            s3key = event["Input"]["Media"]["Images"]["S3Key"]
        workflow_id = str(event["WorkflowExecutionId"])
        asset_id = event['AssetId']
    
    except Exception:
        output_object.update_workflow_status("Error")
        output_object.add_workflow_metadata(BatchImageModerationError="No valid inputs")
        raise MasExecutionError(output_object.return_output_object())
    
    valid_image_types = [".json"]
    file_type = os.path.splitext(s3key)[1]
    
    # Image batch processing is synchronous.
    if file_type in valid_image_types:
        
        # Read metadata and list of frames
        chunk_details = json.loads(s3.get_object( Bucket=s3bucket, Key=s3key, )["Body"].read())        
        chunk_result = []
        for img_s3key in chunk_details['s3_original_frames_keys']:
            # For each frame detect text and save the results
            try:
                response = detect_moderation_labels(s3bucket, urllib.parse.unquote_plus(img_s3key))
            except Exception as e:
                output_object.update_workflow_status("Error")
                output_object.add_workflow_metadata(BatchImageModerationError="Unable to make request to rekognition: {e}".format(e=e))
                raise MasExecutionError(output_object.return_output_object())
            else:
                frame_result = []
                for i in response['ModerationLabels']:
                    # Workaround: Fixme later. Adding static bounding box to facilitate interface rendering logic.
                    if len(i['ParentName']) >1:
                        # is a child node
                        i['BoundingBox'] =  {
                                "Width": "1.0",
                                "Height": "1.0",
                                "Left": "0.0",
                                "Top": "0.0"
                        }
                        frame_id, file_extension = os.path.splitext(os.path.basename(img_s3key))
                        frame_result.append({'frame_id': frame_id[3:],
                                    'ModerationLabel': i,
                                    'Timestamp': chunk_details['timestamps'][frame_id]})

                if len(frame_result)>0: chunk_result+=frame_result

            response = {'metadata': chunk_details['metadata'],
                        'frames_result': chunk_result}

            output_object.update_workflow_status("Complete")
            output_object.add_workflow_metadata(AssetId=asset_id, WorkflowExecutionId=workflow_id)
            dataplane = DataPlane()
            metadata_upload = dataplane.store_asset_metadata(asset_id, 'batchModeration', workflow_id, response)

            if metadata_upload["Status"] == "Success":
                print("Uploaded metadata for asset: {asset}".format(asset=asset_id))
            elif metadata_upload["Status"] == "Failed":
                output_object.update_workflow_status("Error")
                output_object.add_workflow_metadata(
                    BatchImageModerationError="Unable to upload metadata for asset: {asset}".format(asset=asset_id))
                raise MasExecutionError(output_object.return_output_object())
            else:
                output_object.update_workflow_status("Error")
                output_object.add_workflow_metadata(
                    BatchImageModerationError="Unable to upload metadata for asset: {asset}".format(asset=asset_id))
                raise MasExecutionError(output_object.return_output_object())
            return output_object.return_output_object()

        else:
            print("ERROR: invalid file type")
            output_object.update_workflow_status("Error")
            output_object.add_workflow_metadata(BatchImageModerationError="Not a valid file type")
            raise MasExecutionError(output_object.return_output_object())
