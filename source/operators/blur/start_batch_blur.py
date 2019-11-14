###############################################################################
# PURPOSE:
#   Lambda function to perform Rekognition tasks on batches of image files
#   It reads a list of frames from a json file - result of frame extraction Lambda
###############################################################################

import os
import cv2
import json
import boto3
import numpy as np
from MediaInsightsEngineLambdaHelper import MasExecutionError
from MediaInsightsEngineLambdaHelper import DataPlane
from MediaInsightsEngineLambdaHelper import MediaInsightsOperationHelper

s3 = boto3.client('s3')


def download_image(s3bucket, s3key):
    temp_image = '/tmp/temp_image'
    with open(temp_image, 'wb') as f:
        s3.download_fileobj(s3bucket, s3key, f)
    f.close()
    return temp_image


def transform(metadata, img, frame_id, frame_width, frame_height, i, padding, detection_type, detection_label):
    nparr = np.fromstring(img, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    for item in metadata:
        # for item in item_list:
        if (item["frame_id"] == str(frame_id)):
            bbox = item[detection_type]['BoundingBox']
            # Set the padding for all four sides of the bounding box (e.g 10.%)
            x1, y1 = (int((float(bbox['Left']) * float(frame_width)) * float(padding)), int((float(bbox['Top']) * float(frame_height)) * float(padding)))
            x2, y2 = (int(x1 + int(float(bbox['Width']) * float(frame_width)) * float(padding)), int(y1 + int(float(bbox['Height']) * float(frame_height)) * float(padding)))
            if item[detection_type][detection_label] == i:
                print('Blur: %s' % item[detection_type][detection_label])
                frame[y1:y2, x1:x2] = cv2.GaussianBlur(frame[y1:y2, x1:x2], (41, 41), 30.0, 30.0)
    frame = cv2.imencode(".jpg", frame)[1]
    return frame


# Lambda function entrypoint:
def lambda_handler(event, context):
    operator_object = MediaInsightsOperationHelper(event)
    workflow_id = str(operator_object.workflow_execution_id)
    asset_id = str(operator_object.asset_id)
    
    try:
        if "Images" in event["Input"]["Media"]:
            s3bucket = event["Input"]["Media"]["Images"]["S3Bucket"]
            s3key = event["Input"]["Media"]["Images"]["S3Key"]
    except Exception:
        operator_object.update_workflow_status("Error")
        operator_object.add_workflow_metadata(BatchBlurError="No valid inputs")
        raise MasExecutionError(operator_object.return_output_object())
    
    try:
        ids = operator_object.configuration['DetectionIds']
        padding = operator_object.configuration['Padding']
        detection_type = operator_object.configuration['DetectionType']
        detection_label = operator_object.configuration['DetectionLabel']
    except Exception as e:
        operator_object.update_workflow_status("Error")
        operator_object.add_workflow_metadata(BatchBlurError=e)
        raise MasExecutionError(operator_object.return_output_object())


    print("Processing s3://" + s3bucket + "/" + s3key)
    valid_image_types = [".json"]
    file_type = os.path.splitext(s3key)[1]

    # Image batch processing is synchronous.
    if file_type in valid_image_types:

        # Read metadata and list of frames
        chunk_details = json.loads(s3.get_object(Bucket=s3bucket, Key=s3key, )["Body"].read())
        print(chunk_details)

        # TODO: test max number of frames processed per lambda
        batch_file = operator_object.configuration['DetectionFile']
        batch_key = f'private/assets/{asset_id}/workflows/{workflow_id}/{batch_file}'
        batch_details = json.loads(s3.get_object(Bucket=s3bucket, Key=batch_key, )["Body"].read())
        print(batch_details)
        blur_frame_keys = []
        frame_counter = 0
        for frame in chunk_details['s3_resized_frame_keys']:
            frame_upload = s3.get_object(Bucket=s3bucket, Key=frame)["Body"].read()
            for i in ids:
                frame_upload = transform(batch_details["frames_result"], frame_upload, frame_counter, batch_details['metadata']["original_frame_width"], batch_details['metadata']["original_frame_height"], i, padding, detection_type, detection_label)
            frame_key = 'private/assets/%s/output/%s/blur/%s/id_%d.jpg' % (asset_id, workflow_id, detection_type, frame_counter)
            s3.put_object(ACL='bucket-owner-full-control', Bucket=s3bucket, Key=frame_key, Body=bytearray(frame_upload))
            blur_frame_keys.append(frame_key)
            frame_counter += 1

        response = {
            'metadata': chunk_details['metadata'],
            's3_blur_frame_keys': blur_frame_keys
        }

        operator_object.update_workflow_status("Complete")
        operator_object.add_workflow_metadata(AssetId=asset_id, WorkflowExecutionId=workflow_id)
        dataplane = DataPlane()
        metadata_upload = dataplane.store_asset_metadata(asset_id, "batchBlur", workflow_id, response)

        if metadata_upload["Status"] == "Success":
            print("Uploaded metadata for asset: {asset}".format(asset=asset_id))
        elif metadata_upload["Status"] == "Failed":
            operator_object.update_workflow_status("Error")
            operator_object.add_workflow_metadata(
                BatchBlurError="Unable to upload metadata for asset: {asset}".format(asset=asset_id))
            raise MasExecutionError(operator_object.return_output_object())
        else:
            operator_object.update_workflow_status("Error")
            operator_object.add_workflow_metadata(
                BatchBlurError="Unable to upload metadata for asset: {asset}".format(asset=asset_id))
            raise MasExecutionError(operator_object.return_output_object())
        return operator_object.return_output_object()

    else:
        print("ERROR: invalid file type")
        operator_object.update_workflow_status("Error")
        operator_object.add_workflow_metadata(BatchBlurError="Not a valid file type")
        raise MasExecutionError(operator_object.return_output_object())