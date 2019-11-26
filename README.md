# Media Insights Engine

Welcome to the preview of the Media Insights Engine (MIE) project!

MIE is a _serverless_ framework to accelerate the development of applications that discover next-generation insights in your video, audio, text, and image resources by utilizing AWS Machine Learning services.  MIE lets builders: 

1. Create media analysis workflows from a library of base operations built on AWS Machine Learning and Media Services such as [Amazon Rekognition](https://aws.amazon.com/rekognition/), [Amazon Transcribe](https://aws.amazon.com/transcribe/), [Amazon Translate](https://aws.amazon.com/translate/), [Amazon Cognito](https://aws.amazon.com/cognito/), [Amazon Polly](https://aws.amazon.com/polly/), and [AWS Elemental MediaConvert](https://aws.amazon.com/mediaconvert/).
2. Execute workflows and store the resulting media and analysis for later use.
3. Query analysis extracted from media.
4. Interactively explore some of the capabilities of MIE using the included content and analysis and search web application.
5. Extend MIE for new applications by adding custom operators and custom data stores. 

# Limits

This preview version of MIE can support workflows on short videos up to 4 minutes in duration. 

# Architecture Overview

Media Insights Engine is a _serverless_ architecture on AWS. The following diagram is an overview of the major components of MIE and how they interact when an MIE workflow is executed.  

![](doc/images/MIE-execute-workflow-architecture.png)


## Workflow API
Triggers the execution of a workflow. Also triggers create, update and delete workflows and operators.  Monitors the status of workflows.

## Control plane
Executes the AWS Step Functions state machine for the workflow against the provided input.  Workflow state machines are generated from MIE operators.  As operators within the state machine are executed, the interact with the MIE data plane to store and retrieve derived asset and metadata generated from the workflow.  

## Operators
Generated state machines that perform media analysis or transformation operation.

## Workflows
Generated state machines that execute a number of operators in sequence.

## Data plane
Stores media assets and their associated metadata that are generated by workflows. 

## Data plane API

Trigger create, update, delete and retrieval of media assets and their associated metadata.

## Data plane pipeline

Stores metadata for an asset that can be retrieved as a single block or pages of data using the objects AssetId and Metadata type.  Writing data to the pipeline triggers a copy of the data to be stored in a **Kinesis Stream**.

### **Data plane pipeline consumer**

A lambda function that consumes data from the data plane pipeline and stores it (or acts on it) in another downstream data store.  Data can be stored in different kind of data stores to fit the data management and query needs of the application.  There can be 0 or more pipeline consumers in a MIE application. 

# Installation / Deployment
Deploy the demo architecture and application in your AWS account and start exploring your media.  

Region| Launch
------|-----
US East (N. Virginia) | [![Launch in us-east-1](doc/images/launch-stack.png)](https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/new?stackName=mie&templateURL=https://rodeolabz-us-east-1.s3.amazonaws.com/media-insights-solution/v0.1.4/cf/media-insights-stack.template)
US West (Oregon) | [![Launch in us-west-2](doc/images/launch-stack.png)](https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/new?stackName=mie&templateURL=https://rodeolabz-us-west-2.s3.amazonaws.com/media-insights-solution/v0.1.4/cf/media-insights-stack.template)


The default settings for the template are configured to deploy the sample web application and all the back-end components it requires.  In addition, you must set the required parameter below.

## Required parameters

**Stack Name**: Name of stack. Defaults to `mie`.

**System Configuration**
* **MaxConcurrentWorkflows**: Maximum number of workflows to run concurrently. When the maximum is reached, additional workflows are added to a wait queue. Defaults to `10`.

**Operators** 
* **Enable Operator Library Deployment**: If set to true, deploys the operator library. Defaults to `true`.

**Workflows**
* **DeployTestWorkflow**: If set to true, deploys test workflow which contains operator, stage and workflow stubs for integration testing. Defaults to `false`.
* **DeployInstantTranslateWorkflow**: If set to true, deploys Instant Translate Workflow which takes a video as input and transcribes, translates and creates an audio file in the new language. Defaults to `false`.
* **DeployRekognitionWorkflow**: If set to true, deploys Rekognition Workflows which takes a video as input and transcribes, translates and creates an audio file in the new language. Defaults to `false`.
* **DeployComprehendWorkflow**: If set to true, deploys a Comprehend Workflow which takes text as input and identifies key entities and phrases. Defaults to `false`.
* **DeployKitchenSinkWorkflow**: If set to true, deploys the Kitchen Sink Workflow which contains all MIE operators. Defaults to `true`.

**Sample Applications**
* **DeployDemoSite**: If set to true, deploys a front end application to explore extracted metadata. Defaults to `true`.

**Other parameters**
* **DeployAnalyticsPipeline**: If set to true, deploys a metadata streaming pipeline that can be consumed by downstream analytics plaforms. Defaults to `true`.

## Outputs

After the stack successfully deploys, you can find important interface resources in the **Outputs** tab of the CloudFormation stack.

**DataplaneApiEndpoint** is the endpoint for accessing dataplane APIs to create, update, delete and retrieve media assets

**DataplaneBucket** is the S3 bucket used to store derived media (_derived assets_) and raw analysis metadata created by MIE workflows.

**ElasticsearchEndpoint** is the endpoint of the Elasticsearch cluster used to store analysis metadata for search

**MediaInsightsEnginePython37Layer** is a lambda layer required to build new operator lambdas

**MediaInsightsWebAppUrl** is the Url for the sample Media Insights web application

**WorkflowApiEndpoint** is the endpoint for accessing the Workflow APIs to create, update, delete and execute MIE workflows.

**WorkflowCustomResourceArn** is the custom resource that can be used to create MIE workflows in CloudFormation scripts

# Usage

###  Sample application

![](doc/images/MIEDemo.gif)

The Media Insights sample application lets you upload videos, images, audio and text files for content analysis and add the results to a collection that can be searched to find media that has attributes you are looking for.  It runs an MIE workflow that extracts insights using many of the ML content analysis services available on AWS and stores them in a search engine for easy exploration.  A web based GUI is used to search and visualize the resulting data along-side the input media.  The analysis and transformations included in MIE workflow for this application include:

* Proxy encode of videos and separation of video and audio tracks using **AWS Elemental MediaConvert**. 
* Object, scene, and activity detection in images and video using **Amazon Rekognition**. 
* Celebrity detection in images and video using **Amazon Rekognition**
* Face search from a collection of known faces in images and video using **Amazon Rekognition**
* Facial analysis to detect facial features and faces in images and videos to determine things like happiness, age range, eyes open, glasses, facial hair, etc. In video, you can also measure how these things change over time, such as constructing a timeline of the emotions expressed by an actor.  From **Amazon Rekognition**.
* Unsafe content detection using **Amazon Rekognition**. Identify potentially unsafe or inappropriate content across both image and video assets. 
* Convert speech to text from audio and video assets using **Amazon Transcribe**.
* Convert text from one language to another using **Amazon Translate**.
* Identify entities in text using **Amazon Comprehend**. 
* Identify key phrases in text using **Amazon Comprehend**

Data are stored in Amazon Elasticsearch Service and can be retrieved using _Lucene_ queries in the Collection view search page.

### Example use cases for Media Insights Engine
 
MIE is a reusable architecture that can support many different applications.  Examples:
 
* **Content analysis analysis and search** - Detect objects, people, celebrities and sensitive content, transcribe audio and detect entities, relationships and sentiment.  Explore and analyze media using full featured search and advanced data visualization.  This use case is implemented in the included sample application.
* **Automatic Transcribe and Translate** - Generate captions for Video On Demand content using speech recognition.  
* **Content Moderation** - Detect and edit moderated content from videos.

# Developer Quickstart

The Media Insights Engine is built to be extended for new use cases. You can:

* Run existing workflows using custom runtime configurations.
* Create new operators for new types of analysis or transformations of your media.
* Create new workflows using the existing operators and/or your own operators.
* Add new data consumers to provide data management that suits the needs of your application.

See the [Developer Guide](DEVELOPER_QUICK_START.md) for more information on extending the application for a custom use case.

API Reference - Coming soon!

Builder's guide - Coming soon!

# Known Issues

Visit the Issue page in this repository for known issues and feature requests.

# Release History

# Contributing

See the [CONTRIBUTING](CONTRIBUTING.md) file for how to contribute.

# License

See the [LICENSE](LICENSE) file for our project's licensing.

Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
