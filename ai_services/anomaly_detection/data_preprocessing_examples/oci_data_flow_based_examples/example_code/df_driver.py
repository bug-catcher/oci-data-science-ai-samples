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
from example_code.time_series_merge import time_series_merge
from example_code.time_series_join import time_series_join

signer = oci.auth.signers.get_resource_principals_signer()
data_flow_client = oci.data_flow.DataFlowClient(config={}, signer=signer)
object_storage_client = oci.object_storage.ObjectStorageClient(config={}, signer=signer)
SINGLE_DATAFRAME_PROCESSING = "singleDataFrameProcessing"
COMBINE_DATAFRAMES = "combineDataFrames"
JOIN = "join"
MERGE = "merge"
RESERVED_METADATA = ['distinct_categories']

def get_token_path(spark):
    token_key = "spark.hadoop.fs.oci.client.auth.delegationTokenPath"
    token_path = spark.sparkContext.getConf().get(token_key)
    return token_path

def get_authenticated_client(token_path, client):
    if token_path is None:
        # You are running locally, so use our API Key.
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
            elif source["type"] == "database":
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
        phaseInfo = contents["phaseInfo"]
        phase = phaseInfo["phase"]
        if phase == "inference":
            metadata_dependent_raw = get_object(object_storage_client, phaseInfo["connector"]["namespace"], phaseInfo["connector"]["bucket"], phaseInfo["connector"]["objectName"])
            metadata_dependent = json.loads(metadata_dependent_raw)
            for global_variable in RESERVED_METADATA:
                metadata[global_variable] = metadata_dependent[global_variable]
        elif phase == "train":
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
                        if phase == "train":
                            distinct_categories, dfs[step_config["configurations"]["dataframeName"]] = \
                            eval(func_name)(dfs[step_config["configurations"]["dataframeName"]], **step["args"])
                            if 'distinct_categories' not in metadata:
                                metadata["distinct_categories"] = dict()
                            metadata["distinct_categories"][step["args"]["category"]] = distinct_categories
                        elif phase == "inference":
                            step["args"]["distinct_categories"] = metadata["distinct_categories"][step["args"]["category"]]
                            _, dfs[step_config["configurations"]["dataframeName"]] = \
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
                    right = dfs[step_config["configurations"]["mergeConfiguration"]["right"]]
                    dfs[step_config["configurations"]["dataframeName"]] = time_series_merge(left, right)

        # writing it to output destination
        final_df = dfs[contents["outputDestination"]["combinedResult"]]
        final_df.coalesce(1).write.csv(output_path, header=True)

        # writing metadata to metadata bucket during train
        if phase == "train":
            # metadata_connector = f'oci://{phaseInfo["connector"]["bucket"]}@{phaseInfo["connector"]["namespace"]}/{phaseInfo["connector"]["objectName"]}'
            # with open(metadata_connector, "w") as outfile:
            #     outfile.write(metadata)
            object_storage_client.put_object(phaseInfo["connector"]["namespace"], phaseInfo["connector"]["bucket"], phaseInfo["connector"]["objectName"], json.dumps(metadata))

    except Exception as e:
        raise Exception(e)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--response", required=True)
    parser.add_argument("--output_path", required=True)
    args = parser.parse_args()

    spark = SparkSession.builder.appName("DataFlow").getOrCreate()
    token_path = get_token_path(spark)
    object_storage_client = get_authenticated_client(token_path, oci.object_storage.ObjectStorageClient)
    parse_and_process_data_preprocessing_config(
        object_storage_client, spark, args.response, args.output_path)