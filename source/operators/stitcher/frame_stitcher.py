###############################################################################
# PURPOSE:
#   Lambda function to stitch frames of video together into an mp4
#   It reads a list of frames from batchBlur ddb attribute
###############################################################################

import os
import cv2
import json
import boto3
import numpy as np
from collections import deque
from MediaInsightsEngineLambdaHelper import MasExecutionError
from MediaInsightsEngineLambdaHelper import DataPlane
from MediaInsightsEngineLambdaHelper import MediaInsightsOperationHelper

s3 = boto3.client('s3')

bucket = os.environ['DATAPLANE_BUCKET']

def download_image(s3key):
    temp_image = '/tmp/temp_image'
    with open(temp_image, 'wb') as f:
        s3.download_fileobj(bucket, s3key, f)
    f.close()
    return temp_image

# Lambda function entrypoint:
def lambda_handler(event, context):
    operator_object = MediaInsightsOperationHelper(event)
    workflow_id = str(operator_object.workflow_execution_id)
    asset_id = str(operator_object.asset_id)

    dataplane = DataPlane()

    # Call dataplane to retrieve chunk details
    chunk_details = dataplane.retrieve_asset_metadata(asset_id, operator_name='batchBlur')
    
    print(chunk_details)
    
    fps = int(float(chunk_details['results']['metadata']['fps']))
    output_height = int(chunk_details['results']['metadata']['frame_height'])
    output_width = int(chunk_details['results']['metadata']['frame_width'])

    frames = chunk_details['results']['s3_blur_frame_keys']

    sorted_frames = sorted(frames)

    frame_queue = deque(sorted_frames)

    frame_array = []

    while len(frame_queue) > 0:
        current_frame = frame_queue[0]
        img_path = download_image(current_frame)
        image = cv2.imread(img_path)
        frame_array.append(image)
        frame_queue.popleft()
    
    file_name = "{asset_id}.mp4".format(asset_id=asset_id)

    path_out = "/tmp/" + file_name

    out = cv2.VideoWriter(path_out, cv2.VideoWriter_fourcc(*'MP4V'), fps, (output_width, output_height))
    for i in range(len(frame_array)):
            # writing to a image array
            out.write(frame_array[i])
    out.release()

    upload_s3_key = 'private/assets/%s/output/%s' % (asset_id, file_name)

    s3.upload_file(path_out, bucket, upload_s3_key)

    response = {"redactedAssetLocation": upload_s3_key}

    metadata_upload = dataplane.store_asset_metadata(asset_id, "frameStitcher", workflow_id, response)

    if metadata_upload["Status"] == "Success":
        print("Uploaded metadata for asset: {asset}".format(asset=asset_id))
        operator_object.update_workflow_status("Complete")
        operator_object.add_workflow_metadata(AssetId=asset_id, WorkflowExecutionId=workflow_id)
        return operator_object.return_output_object()
    elif metadata_upload["Status"] == "Failed":
        operator_object.update_workflow_status("Error")
        operator_object.add_workflow_metadata(
            FrameStitcherError="Unable to upload metadata for asset: {asset}".format(asset=asset_id))
        raise MasExecutionError(operator_object.return_output_object())
    else:
        operator_object.update_workflow_status("Error")
        operator_object.add_workflow_metadata(
            FrameStitcherError="Unable to upload metadata for asset: {asset}".format(asset=asset_id))
        raise MasExecutionError(operator_object.return_output_object())
