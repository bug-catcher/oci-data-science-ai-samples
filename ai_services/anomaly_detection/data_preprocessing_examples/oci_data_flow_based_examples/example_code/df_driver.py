import oci
import json
import argparse
import pandas as pd

from pyspark.sql import SparkSession
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


signer = oci.auth.signers.get_resource_principals_signer()
dataflow_session = DataflowSession(app_name="DataFlow")
data_flow_client = oci.data_flow.DataFlowClient(config={}, signer=signer)
object_storage_client = \
    oci.object_storage.ObjectStorageClient(config={}, signer=signer)
SINGLE_DATAFRAME_PROCESSING = "singleDataFrameProcessing"
COMBINE_DATAFRAMES = "combineDataFrames"
JOIN = "join"
MERGE = "merge"
RESERVED_METADATA = ['distinct_categories', 'distinct_column_values']
TRAINING = "applyAndFinalize"
INFERENCING = "apply"


# def get_token_path(spark):
#     token_key = "spark.hadoop.fs.oci.client.auth.delegationTokenPath"
#     token_path = spark.sparkContext.getConf().get(token_key)
#     return token_path


# def get_authenticated_client(token_path, client):
#     if token_path is None:
#         # You are running locally, so use our API Key.
#         # TODO: read from local filesystem instead of obj storage in local mode
#         #       support optional profile name. Example: https://github.com/sudharkj/oci-data-science-ai-samples/commit/bedc36f312f3db5990f910d4c93e3b8561412d7a#diff-01004b5cf83417c2b0c1f208746048b2d4931e54ce5b7b55988ba76c285cd439R27-R33
#         config = oci.config.from_file()
#         authenticated_client = client(config)
#     else:
#         # You are running in Data Flow, so use our Delegation Token.
#         with open(token_path) as fd:
#             delegation_token = fd.read()
#         signer = oci.auth.signers.InstancePrincipalsDelegationTokenSigner(
#             delegation_token=delegation_token
#         )
#         authenticated_client = client(config={}, signer=signer)
#     return authenticated_client


def get_object(object_storage_client, namespace, bucket, file):
    get_resp = object_storage_client.get_object(namespace, bucket, file)
    assert get_resp.status in [
        200,
        201,
    ], f"Unable to get object from {bucket}@{namespace}! Response: {get_resp.text}"
    return get_resp.data.text


def parse_and_process_data_preprocessing_config(object_storage_client, spark, get_resp, phase, output_path):
    """
    Data Preprocessing Operation
    Args:
        object_storage_client: the object storage client for communicating with object storage
        spark: entry point for spark application
        get_resp: the parsed response from config json
        phase: the phase info referring training or inferencing
        output_path: the destination of storing processed csv file(s)
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
                # raw_data = get_object(object_storage_client, source["namespace"], source["bucket"], source["objectName"])
                # data = StringIO(raw_data)
                # pd_df = pd.read_csv(data, sep=",")
                # df = spark.createDataFrame(pd_df)
                raw_data_path = f'oci://{source["bucket"]}@{source["namespace"]}/{source["objectName"]}'
                df = spark.read.format("csv").option("header", "true").load(raw_data_path)
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
        if phase == INFERENCING:
            # metadata_dependent_raw = get_object(object_storage_client, phaseInfo["connector"]["namespace"], phaseInfo["connector"]["bucket"], phaseInfo["connector"]["objectName"])
            # metadata_dependent = json.loads(metadata_dependent_raw)
            metadata_path = f'oci://{phaseInfo["connector"]["bucket"]}@{phaseInfo["connector"]["namespace"]}/{phaseInfo["connector"]["objectName"]}'
            metadata_dependent = spark.read.json(metadata_path)
            for global_variable in RESERVED_METADATA:
                metadata[global_variable] = metadata_dependent[global_variable]
        elif phase == TRAINING:
            pass
        else:
            raise Exception("phaseInfo is not correct") 


        # conducting processing steps
        processing_steps = contents["processingSteps"]
        for step_config in processing_steps:
            if step_config["stepType"] == SINGLE_DATAFRAME_PROCESSING:
                for step in step_config["configurations"]["steps"]:
                    func_name = step["stepName"]
                    # one_hot_encoding is speicifc because it is data dependent transformation
                    # Usually one_hot_encoding will be conducted after merge and joining if multiple datasets involves
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
                    # TODO: the preprocessor function returns the file name or mapping of columns to file names(staging info)
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
                    # If inferencing, we should read pre-stored distinct_column_values from metadata pass it for pivoting function
                    elif func_name == "spark_pivoting":
                        if phase == TRAINING:
                            distinct_column_values, dfs[step_config["configurations"]["dataframeName"]] = \
                                eval(func_name)(dfs[step_config["configurations"]["dataframeName"]], **step["args"])
                            flat_distinct_column_values = [item for sublist in distinct_column_values for item in sublist]
                            # if 'distinct_column_values' not in metadata:
                            metadata['distinct_column_values'] = flat_distinct_column_values
                            # else:
                            #     for val in flat_distinct_column_values:
                            #         metadata['distinct_column_values'].append(val)
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
        preprocessed_details = output_path.split('//')[1]
        preprocessed_details = preprocessed_details.split('/')
        bucket_details = preprocessed_details[0].split('@')
        preprocessed_data_prefix_to_column = dict()

        # writing it to output destination
        if (len(sharding_dict) == 0):
            final_df = dfs[contents["outputDestination"]["combinedResult"]]
            final_df.coalesce(1).write.csv(output_path, header=True)
            preprocessed_data_prefix_to_column[preprocessed_details[1]] = final_df.columns
        else:
            # Sharded dfs
            idx = 0
            for df in sharding_dict:
                final_df = dfs[df]
                final_df.coalesce(1).write.csv(
                    output_path+str(idx), header=True)
                preprocessed_data_prefix_to_column[preprocessed_details[1]+str(idx)] = final_df.columns
                idx += 1

        output_processed_data_info = list()
        # writing metadata to metadata bucket during train
        if phase == TRAINING:
            preprocessed_details = output_path.split('//')[1]
            preprocessed_details = preprocessed_details.split('/')
            bucket_details = preprocessed_details[0].split('@')

            preprocessed_data_details = {
                'namespace': bucket_details[1],
                'bucket': bucket_details[0],
                'prefix': preprocessed_details[1]
            }

            list_objects_response = object_storage_client.list_objects(
                namespace_name=preprocessed_data_details['namespace'],
                bucket_name=preprocessed_data_details['bucket'],
                prefix=preprocessed_data_details['prefix'])
            assert list_objects_response.status == 200, \
                f'Error listing objects: {list_objects_response.text}'
            objects_details = list_objects_response.data

            model_ids = []
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
                        "namespace": bucket_details[1],
                        "bucket": bucket_details[0],
                        "columns": columns
                    })
                    try:
                        model_id = ad_utils.train(
                            api_configuration['projectId'],
                            api_configuration['compartmentId'],
                            data_asset_detail)
                        model_ids.append(model_id)
                    except AssertionError as e:
                        print(e)
            metadata['model_ids'] = model_ids
            # TODO: delet this one line below!!!!!
            metadata['test_output'] = output_processed_data_info
            object_storage_client.put_object(
                phaseInfo["connector"]["namespace"],
                phaseInfo["connector"]["bucket"],
                phaseInfo["connector"]["objectName"],
                json.dumps(metadata))
        
        return output_processed_data_info
    except Exception as e:
        raise Exception(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--response", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--output_path", required=True)
    args = parser.parse_args()

    # spark = SparkSession.builder.appName("DataFlow").getOrCreate()
    # token_path = get_token_path(spark)
    spark = get_spark_context(dataflow_session=dataflow_session)
    # object_storage_client = get_authenticated_client(
    #     token_path, oci.object_storage.ObjectStorageClient)
    object_storage_client = get_authenticated_client(
        client=oci.object_storage.ObjectStorageClient,
        dataflow_session=dataflow_session)
    parse_and_process_data_preprocessing_config(
        object_storage_client, spark, args.response, args.phase, args.output_path)
