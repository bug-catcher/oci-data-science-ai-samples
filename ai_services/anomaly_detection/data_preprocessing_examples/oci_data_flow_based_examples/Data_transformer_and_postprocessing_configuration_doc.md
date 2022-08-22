# Data Transformer and Postprocessing Configuration Doc

As is mentioned in the **AD Data Preprocessing: End-to-end Template Design**, AI Core team published an end-to-end solution template to help our customers to build a complete data pipeline composed of data pre-processing and post-processing operations (for example, anomaly detection), which will facilitate deep learning training and inferencing on top of structured data. The whole workflow is driven by a configuration in json, which will be parsed and executed by the driver program. 

Configuration Structure (Tentative)
-----------------------------------

The configuration is composed of the following 5 parts:

<table class="wrapped confluenceTable"><colgroup><col><col></colgroup><tbody><tr><th class="confluenceTh">Section Name</th><th class="confluenceTh">Explanation</th></tr><tr><td class="confluenceTd">inputSources</td><td class="confluenceTd">Connector for input data sources. Currently we support reading data from Object Storage, ATP and ADW.</td></tr><tr><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue"><span class="inline-comment-marker" data-ref="52387ba5-5c3f-4074-bdcb-e7cb27cde7ec">phaseInfo</span><span style="color: rgb(0,51,102);"><span class="inline-comment-marker" data-ref="52387ba5-5c3f-4074-bdcb-e7cb27cde7ec"></span></span></td><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue">A flag specifies whether it's training or inferencing, and connector to metadata source.</td></tr><tr><td class="confluenceTd">processingSteps</td><td class="confluenceTd">Data preprocessing transformers and related input arguments.</td></tr><tr><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue"><span class="inline-comment-marker" data-ref="2f72beed-9a82-4cfc-8906-031d47c4b85d">stagingDestination</span></td><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue">Connector for intermediate processed data storage, which will be used in post-processing steps.</td></tr><tr><td class="confluenceTd">outputDestination</td><td class="confluenceTd">Connector for final output.</td></tr><tr><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue">serviceApiConfiguration (Optional)</td><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue">Configuration required for post-processing steps. For example, arguments for anomaly detection client.</td></tr></tbody></table>

#### inputSources

Dataset(s) input source(s), with **inputSources** as key and an array of dataset(s) information as value.

*   **dataframeName** - the variable name of this data frame will be used in the whole context.
*   **type** - can either be **object-storage** or **oracle**.
*   For object storage, you will require:
    *   **n****amespace** \- the namespace of the target object storage bucket. 
    *   **bucket** - the bucket name. 
    *   **objectName** \- the full path and name of the object. 
*   For oracle, you will require:
    *   **adbId** \- the OCID of your ADW application. 
    *   **tableName** \- name of the table. 
    *   **connectionId** \- the format is **<DBName>\_high**, which can be found under tnsnames.ora of [Wallet](https://docs.oracle.com/en/cloud/paas/autonomous-database/adbsa/connect-download-wallet.html#GUID-B06202D2-0597-41AA-9481-3B174F75D4B1). 
    *   **user** \- the owner of the table. In most cases it will be **admin**. 
    *   **password** \- the password you setup when you download the Wallet. 

#### phaseInfo

The flag indicating whether it is a training or inferencing phase, plus other required input parameters. Here we will include an object storage connector, the workflow will use it to store or read metadata, which is useful for data dependent steps (for example, one-hot encoding).

*   **phase** - can either be **applyAndFinalize** (training) or **apply** (inferencing).
*   **connector** - the connector to object storage. It will be composed of
    *   **n****amespace** - the namespace of the target object storage bucket. Required if it is for object storage.
    *   **bucket** - the bucket name. Required if it is for object storage.
    *   **objectName** \- the full path and name of the object. Required if it is for object storage.

  

#### processingSteps

This will be a list of all the transformations you want to apply. This is the core of the data processing. Every item in the list is a step, and all the steps will be executed in sequence, one after another. Users should make sure the sequence makes sense, or exceptions will be thrown. DPP doesn't responsible for process validation before execution. For each step, you need to specify the following.

*   **stepType** \- can be either **singleDataFrameProcessing** (for transforming on top of single dataframe) or **combineDataFrames** (for merging or joining two dataframes).
*   **configurations** - the configuration related to the step you take, which will include:
    *   **dataframeName** - a name you given to the output of the transformation.
    *   **steps** - a list of all transformers you want to apply to your target dataframe at this time. For each step, there will be:
        *   **stepName** - the name of the transformer you want to apply. It must exactly matches the one you defined in archive. For the full list of offered transformers, please check **Appendix II: List of Transformers**.
        *   **args** \- all the arguments required for the transformer you choose to use. For details about it, check **Appendix II: List of Transformers**.

  

#### stagingDestination

This is where we store intermediate processed data for post processing. Basically these will be dataframes stored in csv format at an assigned object storage bucket. 

*   **combinedResult (optional)** - the final dataframe you want to output. You need to specify this parameter if you only have **one** single dataframe as the output. But if you do sharding, the sharded dataset will be the output automatically, and you don't need this parameter any more.
*   **type** \- can only be **object-storage** for now.
*   **n****amespace** - the namespace of the target object storage bucket. 
*   **bucket** \- the bucket name. 
*   **objectName** \- the full path and name of the object. 

#### outputDestination

This is where the final output comes to, including model\_info, finalized output after inferencing, etc.

*   **type** \- can only be **object-storage** for now.
*   **n****amespace** - the namespace of the target object storage bucket. 
*   **bucket** \- the bucket name. 
*   **objectName** \- the full path and name of the object. 

#### serviceApiConfiguration (optional)

This configuration is for post processing steps, so in theory you can put anything into that. You can check the following configuration example for anomaly detection training.

Configuration Example
---------------------

 Expand source

```java
{
    "inputSources": [
        {
            "dataframeName": "S1",
            "type": "object-storage",
            "namespace":"ax3dvjxgkemg",
            "bucket":"raw-data-bucket",
            "objectName": "dpp-poc-data.csv"
        },
        {
            "dataframeName": "S2",
            "type": "oracle",
            "adbId": "ocid1.autonomousdatabase.oc1.phx.anyhqljsor7l3jiabms3ycjjc4j5seh6h43yom4f4oqw3xluxjwdpkby2z4q",
            "tableName": "S2_1K_JUL20_352PM_UNPIVOTED",
            "connectionId": "transactionprocessing_high",
            "user":"admin",
            "password": "Changemeplease123"
        },
        {
            "dataframeName": "S3",
            "type": "oracle",
            "adbId": "ocid1.autonomousdatabase.oc1.phx.anyhqljtor7l3jiaafhph54js7uz7zrwglmv3ujpicnecymk5r6pk2ncafia",
            "tableName": "S3_1K_JUL20_344PM_PIVOTED",
            "connectionId": "autonomousdatawarehouse_high",
            "user":"admin",
            "password": "Changemeplease123"
        }
    ],
    "phaseInfo": {
        "phase": "applyAndFinalize",
        "connector": {
            "namespace":"ax3dvjxgkemg",
            "bucket":"metadata-store",
            "objectName": "metadata-2.json"
        }
    },
    "processingSteps": [
        {
            "stepType": "singleDataFrameProcessing",
            "configurations": {
                "dataframeName": "S1",
                "steps": [
                    {
                        "stepName": "string_transformation",
                        "args": {
                            "find_string": "NaN",
                            "replace_string": "None",
                            "column": "s3"
                        }
                    },
                    {
                        "stepName": "remove_unnecessary_columns",
                        "args": {
                            "columns_to_remove":"random-1,random-2"
                        }
                    }
                ]
            }
        },
        {
            "stepType": "singleDataFrameProcessing",
            "configurations": {
                "dataframeName": "S2",
                "steps": [
                    {
                        "stepName": "format_timestamp",
                        "args": {}
                    }
                ]
            }
        },
        {
            "stepType": "singleDataFrameProcessing",
            "configurations": {
                "dataframeName": "S3",
                "steps": [
                    {
                        "stepName": "spark_pivoting",
                        "args": {
                            "groupby": "timestamp dim1",
                            "pivot": "sID",
                            "agg": "value:avg"
                        }
                    },
                    {
                        "stepName": "remove_unnecessary_columns",
                        "args": {
                            "columns_to_remove":"s995"
                        }
                    },
                    {
                        "stepName": "one_hot_encoding",
                        "args": {
                            "category": "dim1"
                        }
                    }
                ]
            }
        },
        {
            "stepType": "combineDataFrames",
            "configurations": {
                "dataframeName": "M1",
                "type":"merge",
                "mergeConfiguration":{
                    "left":"S1",
                    "right":"S2"
                }
            }
        },
        {
            "stepType": "combineDataFrames",
            "configurations": {
                "dataframeName": "J1",
                "type":"join",
                "joinConfiguration":{
                    "left":"M1",
                    "right":"S3",
                    "column":"timestamp"
                }
            }
        },
        {
            "stepType": "singleDataFrameProcessing",
            "configurations": {
                "dataframeName": "J1",
                "steps": [
                    {
                        "stepName": "sharding",
                        "args": {
                            "columnNum": "400",
                            "output": "shard"
                        }
                    }
                ]
            }
        }
    ],
    "stagingDestination": {
        "combinedResult":"J1",
        "type": "object-storage",
        "namespace":"ax3dvjxgkemg",
        "bucket": "staging-bucket",
        "folder": "processed_data_folder"
    }, 
    "outputDestination": {
        "type": "object-storage",
        "namespace":"ax3dvjxgkemg",
        "bucket": "processed-data-bucket",
        "objectName": "model_info.json"
    },
    "serviceApiConfiguration": {
        "anomalyDetection": {
            "serviceEndpoint": null,
            "profileName": "DEFAULT",
            "projectId": "ocid1.aianomalydetectionproject.oc1.phx.amaaaaaaor7l3jiazq2qzy57owobjxoru2zsyvboi2cax7o423oesox37kjq",
            "compartmentId": "ocid1.compartment.oc1..aaaaaaaa26brugmo3vvh7tjtyew5pbclnd4i4m2pr7kt2ho7db4gdlzekmha"
        }
    }
}
```

Q&A
---

**Q: Do you plan to support other input/output sources?**

A: In the very long term, we might support other data sources/destinations like S3, Google Cloud Storage. Customers can feel free to contact us at channel #core-datapreprocessing-users for your specific requirement.

  

**Q: Now that you only support object storage as the output, do you plan to add other types in the future?**

A: Yes, but we are more likely to wait and see what our customer really requires. Feel free to contact us at channel #core-datapreprocessing-users for your specific requirement.

  

**Q: For various processing steps, are they order sensitive? How do you ensure the validity of the execution sequence?**

A: Yes, you should make sure you have a valid sequence of all the steps, since we execute them one after another. For midterm solution, we don't do validation on the configuration. For long term one, service providers (not DPP) should take care of that.

  

**Q: Any suggestion to make the execution of steps valid?**

A: A recommended sequence should be firstly, conducting merge/joining afterwards, and Pivoting and Sharding should be put at the end, if necessary. Of course, be careful about data dependency among various steps.

  

Q: According to the **midterm design doc**, looks like your solution is specific to AD. Is that true?

A: Absolutely not. Remember, the whole midterm solution is deployed under **your** tenancy. This means you have 100% access to all the resources

  

**Q: I don't find the transformer I want, can I contribute to the transformer's repo?**

A: Of course! According to the onboarding doc, you will need to compress all the dependency code into archive.zip, and feel free to add your own code into it. 

Appendix I: Driver Code
-----------------------

Here is a code snippet that can drive the configuration above.

 Expand source

```java
import oci
import json
import argparse
import pandas as pd

from pyspark.sql import functions as F
from io import StringIO
from example_code.remove_unnecessary_columns import remove_unnecessary_columns
from example_code.column_rename import column_rename
from example_code.string_transformations import string_transformation
from example_code.format_timestamp import format_timestamp
from example_code.temporal_differencing import temporal_differencing
from example_code.normalization import normalize_data
from example_code.fixed_window_batching import windowing
from example_code.sliding_window_aggregation import aggregation
from example_code.one_hot_encoding import one_hot_encoding
from example_code.pivoting import spark_pivoting
from example_code.sharding import sharding

from example_code.time_series_merge import time_series_merge
from example_code.time_series_join import time_series_join

from example_code.ad_utils import AdUtils
from example_code.dataflow_utils import DataflowSession, get_spark_context, get_authenticated_client


SINGLE_DATAFRAME_PROCESSING = "singleDataFrameProcessing"
COMBINE_DATAFRAMES = "combineDataFrames"
JOIN = "join"
MERGE = "merge"
RESERVED_METADATA = ['distinct_categories', 'distinct_column_values']
TRAINING = "applyAndFinalize"
INFERENCING = "apply"


def get_object(object_storage_client, namespace, bucket, file):
    get_resp = object_storage_client.get_object(namespace, bucket, file)
    assert get_resp.status in [
        200,
        201,
    ], f"Unable to get object from {bucket}@{namespace}! Response: {get_resp.text}"
    return get_resp.data.text


def parse_and_process_data_preprocessing_config(object_storage_client, spark, get_resp, phase):
    """
    Data Preprocessing Operation
    Args:
        object_storage_client: the object storage client for communicating with object storage
        spark: entry point for spark application
        get_resp: the parsed response from config json
        phase: the phase info referring training or inferencing
        staging_path: the destination of storing processed csv file(s)
        output_path: the destination of storing finalized output like model information
    """
    dfs = dict()
    try:
        contents = json.loads(get_resp)
        '''
        Deal with input sources
        '''
        input_sources = contents["inputSources"]

        # build dictonary: df name: df
        for source in input_sources:
            if source["type"] == "object-storage":
                raw_data = get_object(object_storage_client, source["namespace"], source["bucket"], source["objectName"])
                data = StringIO(raw_data)
                pd_df = pd.read_csv(data, sep=",")
                df = spark.createDataFrame(pd_df)
                df = df.select([F.col(x).alias(x.lower()) for x in df.columns])
                dfs[source["dataframeName"]] = df
            elif source["type"] == "oracle":
                properties = {
                    "adbId": source["adbId"],
                    "dbtable": source["tableName"],
                    "connectionId": source["connectionId"],
                    "user": source["user"],
                    "password": source["password"]}
                df = spark.read \
                    .format("oracle") \
                    .options(**properties) \
                    .load()
                df = df.select([F.col(x).alias(x.lower()) for x in df.columns])
                dfs[source["dataframeName"]] = df

        '''
        Check the phase
        train: hold on until the end of processing steps, saving reserved global variables to metadata
        inference: load the metadata into global variables
        '''
        metadata = dict()
        sharding_dict = list()
        phaseInfo = contents["phaseInfo"]
        finalized_output_info = contents["outputDestination"]
        staging_namespace = contents["stagingDestination"]["namespace"]
        staging_bucket = contents["stagingDestination"]["bucket"]
        staging_folder = contents["stagingDestination"]["folder"]
        staging_path = f'oci://{staging_bucket}@{staging_namespace}/{staging_folder}'

        if phase == INFERENCING:
            metadata_dependent_raw = get_object(object_storage_client, phaseInfo["connector"]["namespace"], phaseInfo["connector"]["bucket"], phaseInfo["connector"]["objectName"])
            metadata_dependent = json.loads(metadata_dependent_raw)
            for global_variable in RESERVED_METADATA:
                metadata[global_variable] = metadata_dependent[global_variable]
        elif phase != TRAINING:
            raise Exception("phaseInfo is not correct")

        # conducting processing steps
        processing_steps = contents["processingSteps"]
        for step_config in processing_steps:
            if step_config["stepType"] == SINGLE_DATAFRAME_PROCESSING:
                for step in step_config["configurations"]["steps"]:
                    func_name = step["stepName"]
                    # one_hot_encoding and sharding are specific because it is data dependent transformation
                    # Usually one_hot_encoding will be conducted after merge and joining if multiple datasets involves
                    # TODO: for both cases, we need to add UNKNOWN category if it doesn't exist in training data
                    if func_name == "one_hot_encoding":
                        # if it's training, we will put all the distinct categories of the specific column to metadata for later usage
                        if phase == TRAINING:
                            distinct_categories, dfs[step_config["configurations"]["dataframeName"]] = \
                                eval(func_name)(dfs[step_config["configurations"]["dataframeName"]], **step["args"])
                            if 'distinct_categories' not in metadata:
                                metadata["distinct_categories"] = dict()
                            metadata["distinct_categories"][step["args"]["category"]] = distinct_categories
                        elif phase == INFERENCING:
                            step["args"]["distinct_categories"] = metadata["distinct_categories"][step["args"]["category"]]
                            _, dfs[step_config["configurations"]["dataframeName"]] = \
                                eval(func_name)(dfs[step_config["configurations"]["dataframeName"]], **step["args"])
                    # sharding also needs to be specially treated. We need:
                    # 1. Check whether it's the last one of the processing_steps
                    # 2. Saving multiple dataframes
                    elif func_name == "sharding":
                        step_config_len = len(step_config["configurations"]["steps"]) - 1
                        if (step_config["configurations"]["steps"]).index(step) != step_config_len:
                            raise Exception("Sharding must be the last of processing steps")
                        sharding_dfs = eval(func_name)(dfs[step_config["configurations"]["dataframeName"]], **step["args"])
                        sharding_dict = list(sharding_dfs.keys())
                        dfs.update(sharding_dfs)
                    # Pivoting also needs specific treatment since it's also a data dependent processing
                    # Usually pivoting will be conducted after merge and joining if multiple datasets involves
                    # If training, we should pick out the distinct item of assigned column and store it inside metadata
                    # If inferencing, we should read pre-stored distinct_column_values
                    # from metadata pass it for pivoting function
                    elif func_name == "spark_pivoting":
                        if phase == TRAINING:
                            distinct_column_values, dfs[step_config["configurations"]["dataframeName"]] = \
                                eval(func_name)(dfs[step_config["configurations"]["dataframeName"]], **step["args"])
                            flat_distinct_column_values = [item for sublist in distinct_column_values for item in sublist]
                            metadata['distinct_column_values'] = flat_distinct_column_values
                        elif phase == INFERENCING:
                            step['args']['distinct_column_values'] = metadata['distinct_column_values']
                            _, dfs[step_config['configurations']['dataframeName']] = \
                                eval(func_name)(dfs[step_config["configurations"]["dataframeName"]], **step["args"])
                    else:
                        dfs[step_config["configurations"]["dataframeName"]] = \
                            eval(func_name)(dfs[step_config["configurations"]["dataframeName"]], **step["args"])
            elif step_config["stepType"] == COMBINE_DATAFRAMES:
                if step_config["configurations"]["type"] == JOIN:
                    left = dfs[step_config["configurations"]["joinConfiguration"]["left"]]
                    right = dfs[step_config["configurations"]["joinConfiguration"]["right"]]
                    dfs[step_config["configurations"]["dataframeName"]] = time_series_join([left, right])
                elif step_config["configurations"]["type"] == MERGE:
                    left = dfs[step_config["configurations"]["mergeConfiguration"]["left"]]
                    right = \
                        dfs[step_config["configurations"]["mergeConfiguration"]["right"]]
                    dfs[step_config["configurations"]["dataframeName"]] = \
                        time_series_merge(left, right)

        # prepare the staging file path
        # preprocessed_details = staging_path.split('//')[1]
        # preprocessed_details = preprocessed_details.split('/')
        # bucket_details = preprocessed_details[0].split('@')
        staging_namespace = contents["stagingDestination"]["namespace"]
        staging_bucket = contents["stagingDestination"]["bucket"]
        staging_folder = contents["stagingDestination"]["folder"]
        preprocessed_data_prefix_to_column = dict()

        # writing it to output destination
        if (len(sharding_dict) == 0):
            final_df = dfs[contents[
                "stagingDestination"]["combinedResult"]]
            final_df.coalesce(1).write.csv(staging_path, header=True)
            preprocessed_data_prefix_to_column[
                staging_folder] = final_df.columns
        else:
            # Sharded dfs
            idx = 0
            for df in sharding_dict:
                final_df = dfs[df]
                final_df.coalesce(1).write.csv(
                    staging_path+str(idx), header=True)
                preprocessed_data_prefix_to_column[
                    staging_folder+str(idx)] = final_df.columns
                idx += 1

        output_processed_data_info = list()
        # writing metadata to metadata bucket during train
        if phase == TRAINING:
            preprocessed_data_details = {
                'namespace': staging_namespace,
                'bucket': staging_bucket,
                'prefix': staging_folder
            }

            list_objects_response = object_storage_client.list_objects(
                namespace_name=preprocessed_data_details['namespace'],
                bucket_name=preprocessed_data_details['bucket'],
                prefix=preprocessed_data_details['prefix'])
            assert list_objects_response.status == 200, \
                f'Error listing objects: {list_objects_response.text}'
            objects_details = list_objects_response.data

            model_ids = list()
            api_configuration = \
                contents["serviceApiConfiguration"]["anomalyDetection"]
            ad_utils = AdUtils(dataflow_session,
                               api_configuration['profileName'],
                               api_configuration['serviceEndpoint'])
            data_asset_detail = preprocessed_data_details
            data_asset_detail.pop('prefix')
            for object_details in objects_details.objects:
                if object_details.name.endswith('.csv'):
                    prefix = object_details.name.split('/')[0]
                    if prefix not in preprocessed_data_prefix_to_column:
                        continue
                    columns = preprocessed_data_prefix_to_column[prefix]
                    data_asset_detail['object'] = object_details.name
                    output_processed_data_info.append({
                        "object": object_details.name,
                        "namespace": staging_namespace,
                        "bucket": staging_bucket,
                        "columns": columns
                    })
                    try:
                        model_id = ad_utils.train(
                            api_configuration['projectId'],
                            api_configuration['compartmentId'],
                            data_asset_detail)
                        model_ids.append({
                            "model_id": model_id,
                            "columns": columns
                        })
                    except AssertionError as e:
                        print(e)

            object_storage_client.put_object(
                phaseInfo["connector"]["namespace"],
                phaseInfo["connector"]["bucket"],
                phaseInfo["connector"]["objectName"],
                json.dumps(metadata))

            object_storage_client.put_object(
                finalized_output_info["namespace"],
                finalized_output_info["bucket"],
                finalized_output_info["objectName"],
                json.dumps(model_ids)
            )

        return output_processed_data_info
    except Exception as e:
        raise Exception(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--response", required=True)
    parser.add_argument("--phase", required=True)
    args = parser.parse_args()

    spark = get_spark_context(dataflow_session=dataflow_session)

    object_storage_client = get_authenticated_client(
        client=oci.object_storage.ObjectStorageClient,
        dataflow_session=dataflow_session)
    parse_and_process_data_preprocessing_config(
        object_storage_client, spark, args.response, args.phase)

```

  

Appendix II: List of Transformers
---------------------------------

<table class="wrapped confluenceTable"><colgroup><col><col></colgroup><tbody><tr><th class="confluenceTh">Methods</th><th class="confluenceTh">Usage Description</th></tr><tr><td class="confluenceTd"><a href="https://github.com/oracle-samples/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/example_code/string_transformations.py" class="external-link" rel="nofollow">string_transformation</a></td><td class="confluenceTd">Perform basic string replacement on a particular or set of columns.</td></tr><tr><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue"><a href="https://github.com/oracle-samples/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/example_code/remove_unnecessary_columns.py" title="" class="external-link" rel="nofollow">remove_unnecessary_columns</a></td><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue"><span style="color: rgb(36,41,47);" title="">Remove specified column(s) in your csv file.</span></td></tr><tr><td class="confluenceTd"><a class="external-link" href="https://github.com/oracle-samples/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/example_code/format_timestamp.py" rel="nofollow" style="text-decoration: none;" title="Follow link">format_timestamp</a></td><td class="confluenceTd"><span style="color: rgb(36,41,47);">Convert a column containing date or time information to ISO 8601 format.</span></td></tr><tr><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue"><a class="external-link" href="https://github.com/oracle-samples/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/example_code/time_series_join.py" rel="nofollow" style="text-decoration: none;" title="">time_series_join</a></td><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue">You have multiple time series with different signals corresponding to the same timestamps.</td></tr><tr><td colspan="1" class="confluenceTd"><a href="https://github.com/bug-catcher/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/example_code/time_series_merge.py" class="external-link" rel="nofollow">time_series_merge</a></td><td colspan="1" class="confluenceTd">You have multiple time series with the same set of signals but different timestamps.</td></tr><tr><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue"><a class="external-link" href="https://github.com/oracle-samples/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/example_code/temporal_differencing.py" rel="nofollow" style="text-decoration: none;" title="">temporal_differencing</a></td><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue">Temporally differentiate the data on a desired predefined rate.</td></tr><tr><td class="confluenceTd"><a class="external-link" href="https://github.com/oracle-samples/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/example_code/normalization.py" rel="nofollow" style="text-decoration: none;" title="Follow link">normalize_data</a></td><td class="confluenceTd">Scale numeric features and normalize them into (0, 1) range for training ML/DL models.</td></tr><tr><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue"><a class="external-link" href="https://github.com/oracle-samples/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/example_code/fixed_window_batching.py" rel="nofollow" style="text-decoration: none;" title="">windowing</a></td><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue">Chunking a large file/table that has more than 300k data points to break it down into equal sized chunks.</td></tr><tr><td class="confluenceTd"><a class="external-link" href="https://github.com/oracle-samples/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/example_code/sliding_window_aggregation.py" rel="nofollow" style="text-decoration: none;" title="Follow link">aggregation</a></td><td class="confluenceTd">Process a set of data by&nbsp;<span style="color: rgb(36,41,47);">applying a sliding window.</span></td></tr><tr><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue"><a class="external-link" href="https://github.com/oracle-samples/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/example_code/one_hot_encoding.py" rel="nofollow" style="text-decoration: none;" title="">one_hot_encoding</a></td><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue">Takes on a number of different categories and decompose it into a set of 1 or 0 values columns.</td></tr><tr><td class="confluenceTd"><a class="external-link" href="https://github.com/oracle-samples/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/example_code/pivoting.py" rel="nofollow" style="text-decoration: none;" title="Follow link">spark_pivoting</a></td><td class="confluenceTd">Transfer distinct signal values stored in one column into multiple single dimensional (/Univariate) time series data sets.</td></tr><tr><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue"><a class="external-link" href="https://github.com/oracle-samples/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/example_code/sharding.py" rel="nofollow" style="text-decoration: none;" title="">sharding</a></td><td class="highlight-blue confluenceTd" data-highlight-colour="blue" title="Background colour : Blue">Perform vertical partitioning on datasets with large number of columns</td></tr></tbody></table>

A bunch of sample input & output can be found [here](https://confluence.oci.oraclecorp.com/display/OCAS/Introduction+to+Transformers+for+Data+Preprocessing).

#### string\_transformation

Perform basic string replacement on a particular or set of columns. The output will be the processed dataframe.

**Parameters**

*   **find\_string** \- the value in the existing column that you want to replace.
*   **replace\_string** - the value that you want to use to substitute the find\_string.
*   **column** - the target column(s) you want to perform the replacement. If you want to find and replace in multiple columns, splitting each column with white space in between.

More detailed description and example code can be found [here](https://github.com/bug-catcher/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/string_replacement.md).

  

#### remove\_unnecessary\_columns

You can use it to remove specified column(s) in your csv.

**Parameters**

*   **columns\_to\_remove** - all the column(s) that you want to remove. If you want to find and replace in multiple columns, splitting each column with commas (",") in between.

More detailed description and example code can be found [here](https://github.com/bug-catcher/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/remove_unnecessary_columns.md).

  

#### format\_timestamp

You want to convert a column containing date or time information to ISO 8601 format. No input parameter is required, but your dataframe must have a column called "timestamp" (case **NOT** sensitive).

More detailed description and example code can be found [here](https://github.com/bug-catcher/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/date_time_conversion.md).

  

#### time\_series\_join

You have multiple time series with different signals corresponding to the same timestamps. We are only conducting outer join for now.

**Parameters**

*   **left** - left dataframe of the joint.
*   **right** - right dataframe of the joint.
*   **column** - the basis column of this joint. For now, we only support join over column "timestamp".

More detailed description and example code can be found [here](https://github.com/bug-catcher/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/time_series_join.md).

  

**time\_series\_merge**

You have multiple time series with the same set of signals but different timestamps. Notice we can only merge on "timestamp" column for now.

**Parameters**

*   **left** - left dataframe of the joint.
*   **right** - right dataframe of the joint.

More detailed description and example code can be found [here](https://github.com/bug-catcher/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/time_series_merge.md).

  

**temporal\_differencing**

The user wants to temporally differentiate the data on a desired predefined rate. Notice we can only support dataset with "timestamp" column for now.

**Parameters**

*   **diff\_factor** \- refers to the temporal difference taken into account. This should be an integer.

More detailed description and example code can be found [here](https://github.com/bug-catcher/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/temporal_differencing.md).

  

**normalize\_data**

The user wants to scale numeric features and normalize them into (0, 1) range for training ML/DL models.

**Parameters**

*   **columns** \- the columns you want to conduct normalization. You can input multiple columns and split them by space " ".
*   **norm** - normalization methods. For now it can be either **minmax** or **standard**.

More detailed description and example code can be found [here](https://github.com/bug-catcher/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/feature_normalization.md).

  

**windowing**

You want to break it down into equal sized chunks, so that you can conduct processing in each chunk using OCI Anomaly Detection service.

**Parameters**

*   **batch\_size** - The size of each chunk.

More detailed description and example code can be found [here](https://github.com/bug-catcher/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/Fixed_window_batching.md).

  

**aggregation**

You want to conduct aggregation computation over a batch of data with sliding window.

**Parameters**

*   **step\_size** - the step size when moving forward.
*   **agg** - grouping functions. For now we offer four functions, **avg**, **sum**, **min**, **max**.
*   **window\_size** - the window size of the processed data per batch.

More detailed description and example code can be found [here](https://github.com/bug-catcher/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/sliding_window_aggregation.md).

  

**one\_hot\_encoding**

You have an attribute that takes on a number of different string values, and you want to decompose it into a set of 1 or 0 values columns.

**Parameters**

*   **category** - the target categories you want to conduct encoding. You can input multiple columns and split them by space " ".

More detailed description and example code can be found [here](https://github.com/bug-catcher/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/one_hot_encoding.md).

  

**spark\_pivoting**

You want the target time series data to be partitioned based on distinct or unique combinations of signal values.

**Parameters**

*   **groupby** - the column (s) you want to used to group by. They will appear in the result dataset.
*   **pivot** - the base column you want to conduct pivoting. Basically it should be a categorized column.
*   **agg** - aggregation function you want to use. Currently we support the following functions, **min**, **max**, **sum**, **first**, **avg**.

More detailed description and example code can be found [here](https://github.com/bug-catcher/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/pivoting.md).

  

**sharding**

You want to vertically split the dataset into multiple ones, especially when you have a large number of columns.

**Parameters**

*   **columnNum** - the maximum number you want for a single output dataframe.

More detailed description and example code can be found [here](https://github.com/bug-catcher/oci-data-science-ai-samples/blob/master/ai_services/anomaly_detection/data_preprocessing_examples/oci_data_flow_based_examples/sharding.md).