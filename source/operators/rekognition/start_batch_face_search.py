###############################################################################
# PURPOSE:
#   Lambda function to perform Rekognition tasks on batches of image files
#   It reads a list of frames from a json file - result of frame extraction
#   First, it detect faces using Rekognition Detect Faces API and them call 
#   Face Rekognition API to identify the persons. 
#   Dependency: cv2
#   WARNING: This function might needs longer Lambda timeouts depending on how many frames should be proceesd.
###############################################################################

import os
import numpy as np
import cv2
import tempfile
import json
import urllib
import boto3
from MediaInsightsEngineLambdaHelper import MediaInsightsOperationHelper
from MediaInsightsEngineLambdaHelper import MasExecutionError
from MediaInsightsEngineLambdaHelper import DataPlane

s3 = boto3.client('s3')
rek = boto3.client('rekognition')


# detect faces
def detect_faces(bucket, key):
    try:
        response = rek.detect_faces(
            Image={'S3Object': {'Bucket': bucket, 'Name': key}},
            Attributes=['DEFAULT']
        )
    except Exception as e:
        return Exception(e)
    else:
        return response


# Crop faces to recognise using Rekognition
def crop_faces(detected_faces, bucket, key, frame_width, frame_height):
    cropped_faces = []
    for i in detected_faces['FaceDetails']:
        bbox = i['BoundingBox']
        x1,y1 = ( int(bbox['Left'] * frame_width), int(bbox['Top'] * frame_height) )
        x2,y2 = ( x1 + int(bbox['Width'] * frame_width), y1 + int(bbox['Height'] * frame_height) )

        frame = s3.get_object( Bucket=bucket, Key=key)["Body"].read()
        
        nparr = np.fromstring(frame, np.uint8)
        frame_n = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        # Is a valid coordinate?
        if(x1>0 and x2>0 and y1>0 and y2>0):
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
            r, cropped_face = cv2.imencode(".jpg", frame_n[y1:y2, x1:x2], encode_param)
            cropped_faces.append({'BoundingBox': bbox,'FaceImage': cropped_face})
    return cropped_faces

# search for faces based on the collection
def search_faces_by_image(cropped_img, collection_id):
    try:
        response = rek.search_faces_by_image(
            Image={'Bytes': bytearray(cropped_img)},
            CollectionId=collection_id, 
            MaxFaces=1,
            FaceMatchThreshold=80.0
        )
    except rek.exceptions.InvalidParameterException as ex:
        print(ex)
        # skip no faces exception
        response = {"FaceMatches":[]}
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
        output_object.add_workflow_metadata(BatchFaceSearchError="No valid inputs")
        raise MasExecutionError(output_object.return_output_object())
    
    try:
        collection_id = event["Configuration"]["CollectionId"]
    except KeyError:
        output_object.update_workflow_status("Error")
        output_object.add_workflow_metadata(BatchFaceSearchError="Collection Id is not defined")
        raise MasExecutionError(output_object.return_output_object())

    valid_image_types = [".json"]
    file_type = os.path.splitext(s3key)[1]
    
    # Image batch processing is synchronous.
    if file_type in valid_image_types:
        
        # Read metadata and list of frames
        chunk_details = json.loads(s3.get_object( Bucket=s3bucket, Key=s3key, )["Body"].read())
        frame_width = chunk_details['metadata']['frame_width']
        frame_height = chunk_details['metadata']['frame_height']

        chunk_result = []
        for img_s3key in chunk_details['s3_resized_frame_keys']:

            # For each frame detect text and save the results
            try:
                detected_faces = detect_faces(s3bucket, urllib.parse.unquote_plus(img_s3key))
            except Exception as e:
                output_object.update_workflow_status("Error")
                output_object.add_workflow_metadata(BatchFaceSearchError="Unable to make request to rekognition: {e}".format(e=e))
                raise MasExecutionError(output_object.return_output_object())
            else:
                faces = crop_faces(detected_faces, s3bucket, urllib.parse.unquote_plus(img_s3key), frame_width, frame_height)
                frame_result = []
                for f in faces:
                    try:
                        response = search_faces_by_image(f['FaceImage'], collection_id)
                    except Exception as e:
                        output_object.update_workflow_status("Error")
                        output_object.add_workflow_metadata(
                            BatchFaceSearchError="Unable to make request to rekognition: {e}".format(e=e))
                        raise MasExecutionError(output_object.return_output_object())
                    else:
                        for i in response["FaceMatches"]:
                            frame_id, _ = os.path.splitext(os.path.basename(img_s3key))
                            frame_result.append({'frame_id': frame_id[3:],
                                                'Face': {
                                                    'FaceId': i['Face']['FaceId'],
                                                    'BoundingBox': f['BoundingBox']
                                                },
                                                'Confidence': i['Similarity'],
                                                'ExternalImageId': i['Face']['ExternalImageId'],
                                                'Timestamp': chunk_details['timestamps'][frame_id]})
                if len(frame_result) > 0: chunk_result+=frame_result

            response = {'metadata': chunk_details['metadata'],
                        'frames_result': chunk_result}

            output_object.update_workflow_status("Complete")
            output_object.add_workflow_metadata(AssetId=asset_id, WorkflowExecutionId=workflow_id)
            dataplane = DataPlane()
            metadata_upload = dataplane.store_asset_metadata(asset_id, 'batchFaceSearch', workflow_id, response)

            if metadata_upload["Status"] == "Success":
                print("Uploaded metadata for asset: {asset}".format(asset=asset_id))
            elif metadata_upload["Status"] == "Failed":
                output_object.update_workflow_status("Error")
                output_object.add_workflow_metadata(
                    BatchFaceSearchError="Unable to upload metadata for asset: {asset}".format(asset=asset_id))
                raise MasExecutionError(output_object.return_output_object())
            else:
                output_object.update_workflow_status("Error")
                output_object.add_workflow_metadata(
                    BatchFaceSearchError="Unable to upload metadata for asset: {asset}".format(asset=asset_id))
                raise MasExecutionError(output_object.return_output_object())
            return output_object.return_output_object()

        else:
            print("ERROR: invalid file type")
            output_object.update_workflow_status("Error")
            output_object.add_workflow_metadata(BatchFaceSearchError="Not a valid file type")
            raise MasExecutionError(output_object.return_output_object())
