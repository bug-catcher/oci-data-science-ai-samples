import oci
import json
import argparse
import pandas as pd

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from io import StringIO
from example_code.remove_unnecessary_columns import remove_unnecessary_columns
from example_code.column_rename import column_rename
from example_code.one_hot_encoding import one_hot_encoding
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

from ai_services.anomaly_detection.data_preprocessing_examples.oci_data_flow_based_examples.example_code.ad_utils import \
    AdUtils

signer = oci.auth.signers.get_resource_principals_signer()
data_flow_client = oci.data_flow.DataFlowClient(config={}, signer=signer)
object_storage_client = \
    oci.object_storage.ObjectStorageClient(config={}, signer=signer)
SINGLE_DATAFRAME_PROCESSING = "singleDataFrameProcessing"
COMBINE_DATAFRAMES = "combineDataFrames"
JOIN = "join"
MERGE = "merge"
RESERVED_METADATA = ['distinct_categories']
TRAINING = "applyAndFinalize"
INFERENCING = "apply"


def get_token_path(spark):
    token_key = "spark.hadoop.fs.oci.client.auth.delegationTokenPath"
    token_path = spark.sparkContext.getConf().get(token_key)
    return token_path


def get_authenticated_client(token_path, client):
    if token_path is None:
        # You are running locally, so use our API Key.
        # TODO: read from local filesystem instead of obj storage in local mode
        #       support optional profile name. Example: https://github.com/sudharkj/oci-data-science-ai-samples/commit/bedc36f312f3db5990f910d4c93e3b8561412d7a#diff-01004b5cf83417c2b0c1f208746048b2d4931e54ce5b7b55988ba76c285cd439R27-R33
        config = oci.config.from_file()
        authenticated_client = client(config)
    else:
        # You are running in Data Flow, so use our Delegation Token.
        with open(token_path) as fd:
            delegation_token = fd.read()
        signer = oci.auth.signers.InstancePrincipalsDelegationTokenSigner(
            delegation_token=delegation_token
        )
        authenticated_client = client(config={}, signer=signer)
    return authenticated_client


def get_object(object_storage_client, namespace, bucket, file):
    get_resp = object_storage_client.get_object(namespace, bucket, file)
    assert get_resp.status in [
        200,
        201,
    ], f"Unable to get object from {bucket}@{namespace}! Response: {get_resp.text}"
    return get_resp.data.text


def parse_and_process_data_preprocessing_config(object_storage_client, spark, get_resp, output_path):
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
        phase = phaseInfo["phase"]
        if phase == INFERENCING:
            metadata_dependent_raw = get_object(object_storage_client, phaseInfo["connector"]["namespace"], phaseInfo["connector"]["bucket"], phaseInfo["connector"]["objectName"])
            metadata_dependent = json.loads(metadata_dependent_raw)
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
                    if func_name == "one_hot_encoding":
                        # if it's training, we will put all the distinct categories of the specific column to metadata for later usage
                        if phase == TRAINING:
                            distinct_categories, dfs[step_config["configurations"]["dataframeName"]] = \
                            eval(func_name)(dfs[step_config["configurations"]["dataframeName"]], **step["args"])
                            if 'distinct_categories' not in metadata:
                                metadata["distinct_categories"] = dict()
                            metadata["distinct_categories"][step["args"]["category"]] = distinct_categories
                        elif phase == "inference":
                            step["args"]["distinct_categories"] = metadata["distinct_categories"][step["args"]["category"]]
                            _, dfs[step_config["configurations"]["dataframeName"]] = \
                                eval(func_name)(dfs[step_config["configurations"]["dataframeName"]], **step["args"])
                    # sharding also needs to be specially treated. We need:
                    # 1. Check whether it's the last one of the processing_steps
                    # 2. Saving multiple dataframes
                    # TODO: Check in sharding program to make sure user
                    elif func_name == "sharding":
                        step_config_len = len(step_config["configurations"]["steps"]) - 1
                        if (step_config["configurations"]["steps"]).index(step) != step_config_len:
                            raise Exception("Sharding must be the last of processing steps")
                        sharding_dfs = eval(func_name)(dfs[step_config["configurations"]["dataframeName"]], **step["args"])
                        sharding_dict = list(sharding_dfs.keys())
                        dfs.update(sharding_dfs)
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

        # writing it to output destination
        if (len(sharding_dict) == 0):
            final_df = dfs[contents["outputDestination"]["combinedResult"]]
            final_df.coalesce(1).write.csv(output_path, header=True)
        else:
            # Sharded dfs
            idx = 0
            for df in sharding_dict:
                final_df = dfs[df]
                final_df.coalesce(1).write.csv(
                    output_path+str(idx), header=True)
                idx += 1

        # writing metadata to metadata bucket during train
        if phase == TRAINING:
            preprocessed_details = output_path.split('//')[1]
            preprocessed_details = preprocessed_details.split('/')
            bucket_details = preprocessed_details[0].split('@')
            ad_utils = AdUtils(profile_name=phaseInfo['profile_name'], service_endpoint=phaseInfo['service_endpoint'])
            data_asset_details = {
                'namespace': bucket_details[1],
                'bucket': bucket_details[0],
                'prefix': preprocessed_details[1]
            }
            model_ids = ad_utils.train(project_id=phaseInfo['project_id'], compartment_id=phaseInfo['compartment_id'],
                                       data_assets=data_asset_details)
            metadata['model_ids'] = model_ids
            object_storage_client.put_object(
                phaseInfo["connector"]["namespace"],
                phaseInfo["connector"]["bucket"],
                phaseInfo["connector"]["objectName"],
                json.dumps(metadata))

    except Exception as e:
        raise Exception(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--response", required=True)
    parser.add_argument("--output_path", required=True)
    args = parser.parse_args()

    spark = SparkSession.builder.appName("DataFlow").getOrCreate()
    token_path = get_token_path(spark)
    object_storage_client = get_authenticated_client(
        token_path, oci.object_storage.ObjectStorageClient)
    parse_and_process_data_preprocessing_config(
        object_storage_client, spark, args.response, args.output_path)
