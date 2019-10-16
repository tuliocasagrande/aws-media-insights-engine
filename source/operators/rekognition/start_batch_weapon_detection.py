###############################################################################
# PURPOSE:
#   Lambda function to perform Rekognition tasks on batches of image files
#   It reads a list of frames from a json file - result of frame extraction Lambda -
#   and uses Rekognition Labels API to detect weapons and filter the results per:
#   ['Weaponry', 'Weapon', 'Handgun', 'Gun']
#   WARNING: This function might needs longer Lambda timeouts depending on how many frames should be proceesd.
###############################################################################

import os
import json
import urllib
import boto3
from MediaInsightsEngineLambdaHelper import MediaInsightsOperationHelper
from MediaInsightsEngineLambdaHelper import MasExecutionError
from MediaInsightsEngineLambdaHelper import DataPlane


s3 = boto3.client('s3')

def detect_labels(bucket, key):
    # Recognizes labels in an image
    rek = boto3.client('rekognition')
    try:
        response = rek.detect_labels(Image={'S3Object':{'Bucket':bucket, 'Name':key}})
    except Exception as e:
        return Exception(e)
    else:
        return response

# Detect guns using Rekognition Detect Labels API, filtering by: ['Weaponry', 'Weapon', 'Handgun', 'Gun']
def detect_guns(labels):
    if labels['Name'] in ['Weaponry', 'Weapon', 'Handgun', 'Gun'] and len(labels['Instances']) > 0:
        return labels
    else:
        return {}

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
        output_object.add_workflow_metadata(BatchWeaponDetection="No valid inputs")
        raise MasExecutionError(output_object.return_output_object())
    
    valid_image_types = [".json"]
    file_type = os.path.splitext(s3key)[1]
    
    # Image batch processing is synchronous.
    if file_type in valid_image_types:
        
        # Read metadata and list of frames
        chunk_details = json.loads(s3.get_object(Bucket=s3bucket, Key=s3key, )["Body"].read())
        chunk_result = []
        for img_s3key in chunk_details['s3_resized_frame_keys']:
            try:
                response = detect_labels(s3bucket, urllib.parse.unquote_plus(img_s3key))
            except Exception as e:
                output_object.update_workflow_status("Error")
                output_object.add_workflow_metadata(BatchWeaponDetection="Unable to make request to rekognition: {e}".format(e=e))
                raise MasExecutionError(output_object.return_output_object())
            else:
                frame_result = {}
                for item in response['Labels']:
                    weapons = detect_guns(item)
                    if 'Instances' in weapons:
                        bbox = weapons['Instances'][0]['BoundingBox']
                        frame_id, _ = os.path.splitext(os.path.basename(img_s3key))
                        frame_result = {'frame_id': frame_id[3:],
                                             'Weapon': {
                                                'BoundingBox': bbox
                                             },
                                             'Confidence': weapons['Confidence'],
                                             'Name': weapons['Name'],
                                             'Timestamp': chunk_details['timestamps'][frame_id]}

                if len(frame_result)>0: chunk_result.append(frame_result)


            response = {'metadata': chunk_details['metadata'],
                        'frames_result': chunk_result}

            output_object.update_workflow_status("Complete")
            output_object.add_workflow_metadata(AssetId=asset_id, WorkflowExecutionId=workflow_id)

            dataplane = DataPlane()
            metadata_upload = dataplane.store_asset_metadata(asset_id, 'batchWeaponDetection', workflow_id, response)
            print("This is my response data:{}".format(response))
            print(metadata_upload)

            if metadata_upload["Status"] == "Success":
                print("Uploaded metadata for asset: {asset}".format(asset=asset_id))
            elif metadata_upload["Status"] == "Failed":
                output_object.update_workflow_status("Error")
                output_object.add_workflow_metadata(
                    BatchWeaponDetection="Unable to upload metadata for asset: {asset}".format(asset=asset_id))
                raise MasExecutionError(output_object.return_output_object())
            else:
                output_object.update_workflow_status("Error")
                output_object.add_workflow_metadata(
                    BatchWeaponDetection="Unable to upload metadata for asset: {asset}".format(asset=asset_id))
                raise MasExecutionError(output_object.return_output_object())
            return output_object.return_output_object()

        else:
            print("ERROR: invalid file type")
            output_object.update_workflow_status("Error")
            output_object.add_workflow_metadata(BatchWeaponDetection="Not a valid file type")
            raise MasExecutionError(output_object.return_output_object())
